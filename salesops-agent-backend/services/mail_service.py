"""Mail infrastructure: IMAP receive, SMTP send (spec E1, E4, E6).

Blocking stdlib (imaplib/smtplib) runs in asyncio.to_thread.  Credentials are
decrypted here at use time and never logged or returned (AGENTS.md §3.3).
Sync is strictly read-only against the remote mailbox (readonly SELECT).
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.mime.text import MIMEText
from email.utils import make_msgid, parsedate_to_datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.user_config import (
    ConfigurationMissing,
    ResolvedEmailConfig,
    resolve_email_config,
)
from db.models import MailDraft, MailMessage

logger = logging.getLogger(__name__)

IMAP_PORT = 993
MAX_SYNC_MESSAGES = 50
MAX_BODY_CHARS = 20_000
SEND_TIMEOUT_SECONDS = 30

# Providers whose IMAP host is not a mechanical smtp→imap rewrite.
KNOWN_IMAP_HOSTS = {
    "smtp.gmail.com": "imap.gmail.com",
    "smtp.mail.yahoo.com": "imap.mail.yahoo.com",
    "smtp.outlook.com": "imap-mail.outlook.com",
}


class MailSyncError(Exception):
    """Inbox could not be read — message is safe to show the user."""


class MailSendError(Exception):
    """SMTP send failed — message is safe to show the user."""


class SyncResult(BaseModel):
    synced: int
    skipped_duplicates: int
    errors: list[str]


@dataclass
class ParsedMail:
    uid: int
    message_id: str | None
    from_addr: str
    to_addrs: str
    subject: str
    body_text: str
    received_at: datetime


# ── Pure helpers ──────────────────────────────────────────────────────────


def derive_imap_host(smtp_host: str | None) -> str:
    """Map a configured SMTP host to its IMAP counterpart (spec E1)."""
    if not smtp_host:
        raise MailSyncError(
            "Your email settings have no SMTP host, so the inbox host cannot "
            "be derived. Update Settings → Email."
        )
    host = smtp_host.strip().lower()
    if host in KNOWN_IMAP_HOSTS:
        return KNOWN_IMAP_HOSTS[host]
    if host.startswith("smtp."):
        return "imap." + host[len("smtp."):]
    return host


def _strip_html(raw: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", no_tags).strip()


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def extract_body_text(msg: Message) -> str:
    """First text/plain part; fall back to tag-stripped text/html."""
    parts = [msg] if not msg.is_multipart() else list(msg.walk())
    text = "".join(
        _decode_payload(p) for p in parts if p.get_content_type() == "text/plain"
    )
    if not text:
        text = "".join(
            _strip_html(_decode_payload(p))
            for p in parts
            if p.get_content_type() == "text/html"
        )
    return text.strip()[:MAX_BODY_CHARS]


def _parse_date(msg: Message) -> datetime:
    try:
        parsed = parsedate_to_datetime(msg.get("Date", ""))
        if parsed is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Blocking IMAP / SMTP (run in threads) ─────────────────────────────────


def _fetch_inbox(
    cfg: ResolvedEmailConfig, known_uids: set[int]
) -> tuple[list[ParsedMail], int, list[str]]:
    """Read-only IMAP fetch. Returns (parsed, total_uids, per-message errors)."""
    host = derive_imap_host(cfg.smtp_host)
    if not cfg.smtp_password:
        raise MailSyncError(
            "Your saved email settings have no password, so the inbox cannot "
            "be opened. Re-save Settings → Email with an app password."
        )
    parsed: list[ParsedMail] = []
    errors: list[str] = []
    try:
        with imaplib.IMAP4_SSL(host, IMAP_PORT) as conn:
            conn.login(cfg.email_address, cfg.smtp_password)
            conn.select("INBOX", readonly=True)  # E6: never mutate flags
            status, data = conn.uid("SEARCH", None, "ALL")
            if status != "OK" or not data or not data[0]:
                return parsed, 0, errors
            uids = [int(u) for u in data[0].split()]
            new_uids = [u for u in uids if u not in known_uids]
            for uid in new_uids[-MAX_SYNC_MESSAGES:]:
                try:
                    status, fetched = conn.uid("FETCH", str(uid), "(RFC822)")
                    if status != "OK" or not fetched or fetched[0] is None:
                        errors.append(f"Message UID {uid} could not be fetched.")
                        continue
                    raw = fetched[0][1]
                    msg = email.message_from_bytes(raw)
                    parsed.append(
                        ParsedMail(
                            uid=uid,
                            message_id=msg.get("Message-ID"),
                            from_addr=str(msg.get("From", "")),
                            to_addrs=str(msg.get("To", "")),
                            subject=str(msg.get("Subject", "")),
                            body_text=extract_body_text(msg),
                            received_at=_parse_date(msg),
                        )
                    )
                except (imaplib.IMAP4.error, ValueError, TypeError) as exc:
                    logger.warning("IMAP fetch failed uid=%s: %s", uid, exc)
                    errors.append(f"Message UID {uid} could not be parsed.")
            return parsed, len(uids), errors
    except imaplib.IMAP4.error as exc:
        logger.error("IMAP login/select failed host=%s user=%s: %s",
                     host, cfg.email_address, exc)
        raise MailSyncError(
            f"Could not sign in to {host} with your saved email credentials. "
            "Check Settings → Email (Gmail requires an app password)."
        ) from exc


def _smtp_send(
    cfg: ResolvedEmailConfig,
    draft: MailDraft,
    in_reply_to: str | None,
    references: str | None,
) -> str:
    """Send via the user's own SMTP account. Returns the new Message-ID."""
    msg = MIMEText(draft.body, "plain", "utf-8")
    msg["From"] = cfg.email_address
    msg["To"] = draft.to_addr
    msg["Subject"] = draft.subject
    message_id = make_msgid()
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = f"{references} {in_reply_to}".strip()
    try:
        with smtplib.SMTP_SSL(
            cfg.smtp_host or "", cfg.smtp_port or 465, timeout=SEND_TIMEOUT_SECONDS
        ) as smtp:
            smtp.login(cfg.email_address, cfg.smtp_password or "")
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP send failed host=%s: %s", cfg.smtp_host, exc,
                     exc_info=True)
        raise MailSendError(
            "The reply could not be sent through your email provider. "
            "Check Settings → Email and try again."
        ) from exc
    return message_id


# ── Async orchestration ───────────────────────────────────────────────────


async def sync_inbox(user_id: str, db: AsyncSession) -> SyncResult:
    """Fetch new inbox messages into mail_messages (dedup by IMAP UID)."""
    cfg = await resolve_email_config(user_id, db)
    if cfg is None:
        raise ConfigurationMissing(
            "Email is not configured. Go to Settings → Email and add your "
            "SMTP details to enable inbox sync."
        )

    existing = await db.execute(
        select(MailMessage.imap_uid).where(
            MailMessage.user_id == user_id,
            MailMessage.imap_uid.is_not(None),
        )
    )
    known_uids = {uid for uid in existing.scalars().all() if uid is not None}

    parsed, total_uids, errors = await asyncio.to_thread(
        _fetch_inbox, cfg, known_uids
    )

    for m in parsed:
        db.add(
            MailMessage(
                user_id=user_id,
                direction="inbound",
                imap_uid=m.uid,
                message_id=m.message_id,
                from_addr=m.from_addr,
                to_addrs=m.to_addrs,
                subject=m.subject,
                body_text=m.body_text,
                received_at=m.received_at,
            )
        )
    await db.commit()

    return SyncResult(
        synced=len(parsed),
        skipped_duplicates=max(total_uids - len(parsed) - len(errors), 0),
        errors=errors,
    )


async def send_reply(
    user_id: str, draft: MailDraft, db: AsyncSession
) -> MailMessage:
    """Approve-and-send (spec E4): SMTP send + outbound copy in Sent."""
    cfg = await resolve_email_config(user_id, db)
    if cfg is None or not cfg.smtp_host or not cfg.smtp_password:
        raise ConfigurationMissing(
            "Email is not fully configured (host and password required). "
            "Go to Settings → Email to complete it."
        )

    original: MailMessage | None = None
    if draft.inbound_message_id:
        result = await db.execute(
            select(MailMessage).where(
                MailMessage.id == draft.inbound_message_id,
                MailMessage.user_id == user_id,
            )
        )
        original = result.scalars().first()

    message_id = await asyncio.to_thread(
        _smtp_send,
        cfg,
        draft,
        original.message_id if original else None,
        original.message_id if original else None,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sent = MailMessage(
        user_id=user_id,
        direction="outbound",
        message_id=message_id,
        from_addr=cfg.email_address,
        to_addrs=draft.to_addr,
        subject=draft.subject,
        body_text=draft.body,
        received_at=now,
        read_at=now,
        in_reply_to_id=draft.inbound_message_id,
    )
    db.add(sent)
    await db.flush()

    draft.status = "sent"
    draft.sent_message_id = sent.id
    await db.commit()
    await db.refresh(sent)
    return sent
