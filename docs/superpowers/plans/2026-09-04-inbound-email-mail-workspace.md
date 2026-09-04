# Inbound Email & Gmail-style Mail Workspace — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the sales agent read a user's incoming email (IMAP derived from their SMTP config), generate editable reply drafts for user-selected messages, and send approved drafts via SMTP — inside a Gmail-style Mail workspace (Inbox/Sent/Drafts/Trash).

**Architecture:** Two new user-scoped tables (`mail_messages`, `mail_drafts`) + one Alembic migration. A new `services/mail_service.py` owns IMAP fetch / SMTP send (blocking stdlib in `asyncio.to_thread`). A new `agent_core/inbound_reply_agent.py` (OpenAI Agents SDK, per-user LLM config, existing tracing) creates drafts via a tool. A new `/api/mail` router exposes folder/draft endpoints; Next.js proxies them through a catch-all route and renders the workspace at `/mail`.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / Alembic / imaplib / smtplib / openai-agents · Next.js 16 App Router / TypeScript / Tailwind / shadcn-style ui primitives.

**Spec:** `docs/superpowers/specs/2026-09-04-inbound-email-mail-workspace-design.md`

**Environment notes (verified):** Windows PowerShell — use `;` not `&&`; `uv.exe` is access-denied, use system `python`; backend on port 8000 (`uvicorn main:app --reload --port 8000` from `salesops-agent-backend/`); Next dev on 3001; demo login `demo@querysales.demo` / `Demo1234!`. Alembic head before this plan: `7d8e9f0a1b2c`.

**Spec delta (deliberate):** `mail_messages` gains one extra column `message_id` (RFC-822 Message-ID, nullable) so sent replies can emit proper `In-Reply-To`/`References` headers. Everything else matches the spec.

---

## File Structure

| File | Responsibility |
|---|---|
| `salesops-agent-backend/db/models.py` (modify) | Add `MailMessage`, `MailDraft` ORM models |
| `salesops-agent-backend/alembic/versions/<rev>_add_mail_workspace.py` (create) | Migration for both tables |
| `salesops-agent-backend/services/mail_service.py` (create) | IMAP derive/fetch, body extraction, SMTP send, sync orchestration |
| `salesops-agent-backend/agent_core/inbound_reply_agent.py` (create) | Reply agent + `create_reply_draft_tool` + `run_inbound_reply_agent` |
| `salesops-agent-backend/api/endpoints/mail.py` (create) | `/api/mail` router (folders, messages, drafts) |
| `salesops-agent-backend/main.py` (modify) | Register mail router |
| `salesops-agent-backend/tests/test_mail_service.py` (create) | Unit tests: host derivation, body extraction |
| `querysales-web/lib/types.ts` (modify) | Mail types |
| `querysales-web/app/api/mail/[...segments]/route.ts` (create) | Catch-all auth proxy |
| `querysales-web/components/sidebar.tsx` (modify) | Mail nav item |
| `querysales-web/app/(dashboard)/mail/page.tsx` (create) | Server component: initial inbox fetch |
| `querysales-web/app/(dashboard)/mail/mail-client.tsx` (create) | Workspace state + actions |
| `querysales-web/app/(dashboard)/mail/components/folder-rail.tsx` (create) | Folder list + counts |
| `querysales-web/app/(dashboard)/mail/components/message-list.tsx` (create) | Selectable list + toolbar |
| `querysales-web/app/(dashboard)/mail/components/message-view.tsx` (create) | Full message pane |
| `querysales-web/app/(dashboard)/mail/components/draft-editor.tsx` (create) | Editable draft + send |

---

### Task 1: ORM models + migration

**Files:**
- Modify: `salesops-agent-backend/db/models.py` (append after `OutreachDraft`, ~line 374)
- Create: migration via autogenerate
- Test: `tests/test_mail_service.py` (created in Task 2; here we verify schema)

- [ ] **Step 1: Append the two models to `db/models.py`** (after the `OutreachDraft` class, before `UserIntegrationConfig`):

```python
class MailMessage(Base):
    """One email in the user's Mail workspace — inbound (IMAP sync) or
    outbound (approved reply sent via SMTP).  Trash = trashed_at set."""

    __tablename__ = "mail_messages"
    __table_args__ = (
        Index("ix_mail_messages_user_dir_trashed", "user_id", "direction", "trashed_at"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    direction = Column(String, nullable=False)  # inbound | outbound
    imap_uid = Column(Integer, nullable=True)  # IMAP UID — inbound dedup key
    message_id = Column(String, nullable=True)  # RFC-822 Message-ID (threading)
    from_addr = Column(String, nullable=False, default="")
    to_addrs = Column(String, nullable=False, default="")
    subject = Column(String, nullable=False, default="")
    body_text = Column(Text, nullable=False, default="")
    received_at = Column(DateTime, default=_utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
    trashed_at = Column(DateTime, nullable=True)
    in_reply_to_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class MailDraft(Base):
    """An editable reply draft.  Statuses: draft → sent | discarded.
    Never sent automatically — approval is a separate endpoint."""

    __tablename__ = "mail_drafts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    inbound_message_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=True)
    to_addr = Column(String, nullable=False, default="")
    subject = Column(String, nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    status = Column(String, default="draft", nullable=False)
    sent_message_id = Column(String, ForeignKey("mail_messages.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 2: Generate the migration and READ it**

Run (from `salesops-agent-backend/`):
```
python -m alembic revision --autogenerate -m "add mail workspace tables"
```
Expected: new file in `alembic/versions/`, `down_revision = "7d8e9f0a1b2c"`, creating `mail_messages` + `mail_drafts` with the indexes above and nothing else. If autogenerate shows unrelated diffs, hand-trim the file to only the two tables.

- [ ] **Step 3: Apply and verify**

Run:
```
python -m alembic upgrade head
python -c "from db.models import MailMessage, MailDraft; print(MailMessage.__tablename__, MailDraft.__tablename__)"
```
Expected: upgrade prints the new revision as head; python prints `mail_messages mail_drafts`.

- [ ] **Step 4: Commit**

```
git add salesops-agent-backend/db/models.py salesops-agent-backend/alembic/versions/
git commit -m "feat(mail): MailMessage + MailDraft models and migration"
```

---

### Task 2: `services/mail_service.py` (TDD on pure functions)

**Files:**
- Create: `salesops-agent-backend/tests/test_mail_service.py`
- Create: `salesops-agent-backend/services/mail_service.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_mail_service.py`:

```python
"""Unit tests for mail_service pure helpers (no network, no DB)."""

from email.message import EmailMessage

import pytest

from services.mail_service import (
    MailSyncError,
    derive_imap_host,
    extract_body_text,
)


def test_derive_imap_host_gmail():
    assert derive_imap_host("smtp.gmail.com") == "imap.gmail.com"


def test_derive_imap_host_generic_smtp_prefix():
    assert derive_imap_host("smtp.example.com") == "imap.example.com"


def test_derive_imap_host_no_prefix_used_as_is():
    assert derive_imap_host("mail.example.com") == "mail.example.com"


def test_derive_imap_host_none_raises():
    with pytest.raises(MailSyncError):
        derive_imap_host(None)


def test_extract_body_plain():
    msg = EmailMessage()
    msg.set_content("Hello there")
    assert extract_body_text(msg) == "Hello there"


def test_extract_body_html_fallback_strips_tags():
    msg = EmailMessage()
    msg.set_content("<p>Hi <b>bold</b></p>", subtype="html")
    text = extract_body_text(msg)
    assert "<" not in text
    assert "Hi" in text and "bold" in text


def test_extract_body_prefers_plain_part():
    msg = EmailMessage()
    msg.make_alternative()
    msg.set_content("plain version")
    msg.add_alternative("<p>html version</p>", subtype="html")
    assert "plain version" in extract_body_text(msg)
    assert "html version" not in extract_body_text(msg)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_mail_service.py -v`
Expected: ImportError / ModuleNotFoundError for `services.mail_service`.

- [ ] **Step 3: Implement `services/mail_service.py`**:

```python
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
    return text[:MAX_BODY_CHARS]


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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_mail_service.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```
git add salesops-agent-backend/services/mail_service.py salesops-agent-backend/tests/test_mail_service.py
git commit -m "feat(mail): IMAP sync + SMTP send service with unit tests"
```

---

### Task 3: Inbound reply agent

**Files:**
- Create: `salesops-agent-backend/agent_core/inbound_reply_agent.py`

Reuses `SalesAgentContext` with `lead_id=""` so `search_knowledge_tool` is shared verbatim with the sales agent (no refactor); the inbound agent's tool list excludes lead tools.

- [ ] **Step 1: Implement the agent module**:

```python
"""Inbound reply agent (spec §4.2).

Reads user-selected incoming emails and produces one editable MailDraft per
email via create_reply_draft_tool.  Never sends mail, never touches leads.
Tracing/events reuse agent_core.events + DatabaseTracingProcessor so the
existing run timeline UI works unchanged (Decision D6).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from agents import Agent, Runner
from agents import RunContextWrapper, function_tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from agent_core.events import emit, OBSERVE, REASON, COMPLETE, ERROR
from agent_core.model_factory import build_model
from agent_core.sales_tools import SalesAgentContext, search_knowledge_tool
from agent_core.tracing import flush_pending_writes
from core.user_config import (
    ConfigurationMissing,
    resolve_embedding_config,
    resolve_llm_config,
)
from db.models import MailDraft, MailMessage, WorkflowRun

logger = logging.getLogger(__name__)

MAX_BODY_CHARS_PER_EMAIL = 4000

SYSTEM_PROMPT = """\
You are QuerySales AI, replying to incoming customer emails on behalf of a \
sales professional.

For EVERY incoming email provided in the user message you must:
1. Read the email and identify what the sender actually wants.
2. Optionally call `search_knowledge_tool` to ground facts (pricing, product \
   capabilities, policies) before promising anything.
3. Call `create_reply_draft_tool` exactly once for that email with:
   - inbound_message_id: the email's id from the user message
   - to: the sender's address
   - subject: "Re: <original subject>" (unchanged if already prefixed)
   - body: a professional, warm, concise plain-text reply that answers the \
     sender's questions and proposes a clear next step.

Rules:
- One draft per email, no exceptions.
- Never invent pricing, discounts, or contractual terms not in the knowledge \
  base or the email thread.
- Keep replies under 250 words.
- After creating all drafts, return a one-line summary per email.
"""


@function_tool
async def create_reply_draft_tool(
    ctx: RunContextWrapper[SalesAgentContext],
    inbound_message_id: str,
    to: str,
    subject: str,
    body: str,
) -> str:
    """Save an editable reply draft for one incoming email. Never sends it.

    Args:
        inbound_message_id: id of the incoming email being replied to
        to: recipient address (the original sender)
        subject: reply subject line
        body: plain-text reply body
    """
    cfg = ctx.context
    result = await cfg.db.execute(
        select(MailMessage).where(
            MailMessage.id == inbound_message_id,
            MailMessage.user_id == cfg.user_id,
        )
    )
    if not result.scalars().first():
        return f"Email {inbound_message_id} not found or not owned by you."

    draft = MailDraft(
        user_id=cfg.user_id,
        inbound_message_id=inbound_message_id,
        run_id=cfg.run_id,
        to_addr=to,
        subject=subject,
        body=body,
    )
    cfg.db.add(draft)
    await cfg.db.commit()
    logger.info(
        "create_reply_draft: run=%s email=%s subject='%s'",
        cfg.run_id[:8], inbound_message_id[:8], subject[:60],
    )
    return f"Reply draft created (id: {draft.id}). Status: draft — the user must approve it before sending."


def _build_agent(model) -> Agent:
    return Agent(
        name="InboundReplyAgent",
        instructions=SYSTEM_PROMPT,
        model=model,
        tools=[search_knowledge_tool, create_reply_draft_tool],
    )


async def run_inbound_reply_agent(
    user_id: str,
    message_ids: list[str],
    db: AsyncSession,
) -> tuple[WorkflowRun, list[str]]:
    """Run the reply agent over the given inbound messages.

    Returns (run, draft_ids).  Failures are recorded on the run, never raised
    as 500s from the endpoint.
    """
    try:
        llm_cfg = await resolve_llm_config(user_id, db)
        embed_cfg = await resolve_embedding_config(user_id, db)
    except ConfigurationMissing as exc:
        run = WorkflowRun(
            user_id=user_id,
            workflow_type="inbound_reply",
            status="failed",
            final_result={"error": exc.message},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        await emit(db, run_id=run.id, user_id=user_id, phase=ERROR,
                   title="Configuration missing", detail=exc.message)
        return run, []

    result = await db.execute(
        select(MailMessage).where(
            MailMessage.id.in_(message_ids),
            MailMessage.user_id == user_id,
            MailMessage.direction == "inbound",
        )
    )
    messages = list(result.scalars().all())

    run = WorkflowRun(
        user_id=user_id,
        workflow_type="inbound_reply",
        status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await emit(
        db, run_id=run.id, user_id=user_id, phase=OBSERVE,
        title="Reading selected emails",
        detail=f"{len(messages)} email(s): "
               + "; ".join(m.subject or "(no subject)" for m in messages)[:300],
    )

    try:
        model = build_model(llm_cfg)
        agent = _build_agent(model)
        ctx = SalesAgentContext(
            run_id=run.id, user_id=user_id, lead_id="", db=db, embed_cfg=embed_cfg
        )

        blocks = []
        for m in messages:
            blocks.append(
                f"[id: {m.id}]\nFrom: {m.from_addr}\nTo: {m.to_addrs}\n"
                f"Subject: {m.subject}\nReceived: {m.received_at}\n\n"
                f"{m.body_text[:MAX_BODY_CHARS_PER_EMAIL]}"
            )
        user_message = (
            "Draft a reply for each of the following incoming emails.\n\n"
            + "\n\n---\n\n".join(blocks)
        )

        await emit(db, run_id=run.id, user_id=user_id, phase=REASON,
                   title="Drafting replies",
                   detail=f"Model: {llm_cfg.model}")

        await Runner.run(agent, input=user_message, context=ctx)

        drafts_result = await db.execute(
            select(MailDraft.id).where(MailDraft.run_id == run.id)
        )
        draft_ids = [row[0] for row in drafts_result.all()]

        run.status = "completed"
        run.final_result = {"draft_ids": draft_ids, "message_ids": message_ids}
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        await emit(db, run_id=run.id, user_id=user_id, phase=COMPLETE,
                   title="Reply drafts ready",
                   detail=f"{len(draft_ids)} draft(s) created — review them in Drafts.",
                   payload={"draft_ids": draft_ids})
        await flush_pending_writes()
        return run, draft_ids

    except Exception as exc:
        logger.error("Inbound reply agent failed run=%s: %s", run.id[:8], exc,
                     exc_info=True)
        run.status = "failed"
        run.final_result = {"error": "Reply generation failed. Please try again."}
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await emit(db, run_id=run.id, user_id=user_id, phase=ERROR,
                   title="Reply generation failed",
                   detail="An unexpected error occurred. Please try again.")
        await flush_pending_writes()
        await db.refresh(run)
        return run, []
```

- [ ] **Step 2: Import smoke check**

Run: `python -c "from agent_core.inbound_reply_agent import run_inbound_reply_agent; print('ok')"`
Expected: `ok` (no import errors).

- [ ] **Step 3: Commit**

```
git add salesops-agent-backend/agent_core/inbound_reply_agent.py
git commit -m "feat(mail): inbound reply agent with create_reply_draft tool"
```

---

### Task 4: `/api/mail` endpoints

**Files:**
- Create: `salesops-agent-backend/api/endpoints/mail.py`
- Modify: `salesops-agent-backend/main.py` (router registration)

- [ ] **Step 1: Create `api/endpoints/mail.py`**:

```python
"""Mail workspace endpoints (spec §4.3).

Folders, message actions, and reply-draft lifecycle.  Every query is scoped
to the authenticated user; other users' rows 404 (AGENTS.md §3.2).
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.inbound_reply_agent import run_inbound_reply_agent
from core.security import get_current_user
from db.models import MailDraft, MailMessage, User
from db.session import get_db
from services.mail_service import MailSendError, MailSyncError, sync_inbox, send_reply

logger = logging.getLogger(__name__)

router = APIRouter()

Folder = Literal["inbox", "sent", "trash"]
SNIPPET_CHARS = 200


# ── Pydantic models ───────────────────────────────────────────────────────


class MailMessageListItem(BaseModel):
    id: str
    direction: str
    from_addr: str
    to_addrs: str
    subject: str
    snippet: str
    received_at: str
    read: bool
    trashed: bool


class MailFolderCounts(BaseModel):
    inbox: int
    sent: int
    drafts: int
    trash: int
    inbox_unread: int


class MailListResponse(BaseModel):
    messages: list[MailMessageListItem]
    counts: MailFolderCounts


class MailMessageResponse(MailMessageListItem):
    body_text: str
    in_reply_to_id: Optional[str] = None
    read_at: Optional[str] = None


class SyncResponse(BaseModel):
    synced: int
    skipped_duplicates: int
    errors: list[str]


class GenerateDraftsRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=5)


class GenerateDraftsResponse(BaseModel):
    run_id: str
    status: str
    draft_ids: list[str]
    errors: list[str]


class MailDraftResponse(BaseModel):
    id: str
    inbound_message_id: Optional[str] = None
    run_id: Optional[str] = None
    to_addr: str
    subject: str
    body: str
    status: str
    sent_message_id: Optional[str] = None
    created_at: str
    updated_at: str


class DraftUpdateRequest(BaseModel):
    to_addr: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class DraftCreateRequest(BaseModel):
    to_addr: str
    subject: str = ""
    body: str = ""
    inbound_message_id: Optional[str] = None


class SendDraftResponse(BaseModel):
    draft_id: str
    sent_message_id: str


# ── Helpers ───────────────────────────────────────────────────────────────


def _folder_condition(folder: Folder):
    if folder == "inbox":
        return (MailMessage.direction == "inbound", MailMessage.trashed_at.is_(None))
    if folder == "sent":
        return (MailMessage.direction == "outbound", MailMessage.trashed_at.is_(None))
    return (MailMessage.trashed_at.is_not(None),)


def _list_item(m: MailMessage) -> MailMessageListItem:
    return MailMessageListItem(
        id=m.id,
        direction=m.direction,
        from_addr=m.from_addr,
        to_addrs=m.to_addrs,
        subject=m.subject,
        snippet=m.body_text[:SNIPPET_CHARS],
        received_at=m.received_at.isoformat() if m.received_at else "",
        read=m.read_at is not None,
        trashed=m.trashed_at is not None,
    )


async def _counts(user_id: str, db: AsyncSession) -> MailFolderCounts:
    async def count(*conds) -> int:
        result = await db.execute(
            select(func.count()).select_from(MailMessage).where(
                MailMessage.user_id == user_id, *conds
            )
        )
        return result.scalar() or 0

    drafts_result = await db.execute(
        select(func.count()).select_from(MailDraft).where(
            MailDraft.user_id == user_id, MailDraft.status == "draft"
        )
    )
    return MailFolderCounts(
        inbox=await count(MailMessage.direction == "inbound",
                          MailMessage.trashed_at.is_(None)),
        sent=await count(MailMessage.direction == "outbound",
                         MailMessage.trashed_at.is_(None)),
        drafts=drafts_result.scalar() or 0,
        trash=await count(MailMessage.trashed_at.is_not(None)),
        inbox_unread=await count(MailMessage.direction == "inbound",
                                 MailMessage.trashed_at.is_(None),
                                 MailMessage.read_at.is_(None)),
    )


async def _get_message(message_id: str, user_id: str, db: AsyncSession) -> MailMessage:
    result = await db.execute(
        select(MailMessage).where(
            MailMessage.id == message_id, MailMessage.user_id == user_id
        )
    )
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
    return msg


async def _get_draft(draft_id: str, user_id: str, db: AsyncSession) -> MailDraft:
    result = await db.execute(
        select(MailDraft).where(MailDraft.id == draft_id, MailDraft.user_id == user_id)
    )
    draft = result.scalars().first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


def _draft_response(d: MailDraft) -> MailDraftResponse:
    return MailDraftResponse(
        id=d.id,
        inbound_message_id=d.inbound_message_id,
        run_id=d.run_id,
        to_addr=d.to_addr,
        subject=d.subject,
        body=d.body,
        status=d.status,
        sent_message_id=d.sent_message_id,
        created_at=d.created_at.isoformat() if d.created_at else "",
        updated_at=d.updated_at.isoformat() if d.updated_at else "",
    )


# ── Sync ──────────────────────────────────────────────────────────────────


@router.post("/sync", response_model=SyncResponse)
async def sync_inbox_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await sync_inbox(user.id, db)
    except MailSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SyncResponse(**result.model_dump())


# ── Messages ─────────────────────────────────────────────────────────────


@router.get("/messages", response_model=MailListResponse)
async def list_messages(
    folder: Folder = "inbox",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MailMessage)
        .where(MailMessage.user_id == user.id, *_folder_condition(folder))
        .order_by(MailMessage.received_at.desc())
    )
    messages = result.scalars().all()
    return MailListResponse(
        messages=[_list_item(m) for m in messages],
        counts=await _counts(user.id, db),
    )


@router.get("/messages/{message_id}", response_model=MailMessageResponse)
async def get_message(
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_message(message_id, user.id, db)
    if msg.direction == "inbound" and msg.read_at is None:
        from db.models import _utcnow

        msg.read_at = _utcnow()
        await db.commit()
    item = _list_item(msg)
    return MailMessageResponse(
        **item.model_dump(),
        body_text=msg.body_text,
        in_reply_to_id=msg.in_reply_to_id,
        read_at=msg.read_at.isoformat() if msg.read_at else None,
    )


@router.post("/messages/{message_id}/unread", response_model=MailMessageListItem)
async def mark_unread(
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_message(message_id, user.id, db)
    msg.read_at = None
    await db.commit()
    return _list_item(msg)


@router.post("/messages/{message_id}/trash", response_model=MailMessageListItem)
async def trash_message(
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_message(message_id, user.id, db)
    from db.models import _utcnow

    msg.trashed_at = _utcnow()
    await db.commit()
    return _list_item(msg)


@router.post("/messages/{message_id}/restore", response_model=MailMessageListItem)
async def restore_message(
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_message(message_id, user.id, db)
    msg.trashed_at = None
    await db.commit()
    return _list_item(msg)


@router.delete("/messages/{message_id}")
async def delete_message_permanently(
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_message(message_id, user.id, db)
    if msg.trashed_at is None:
        raise HTTPException(
            status_code=409, detail="Only trashed messages can be deleted permanently."
        )
    # Detach referencing drafts so the FK never blocks the delete.
    await db.execute(
        update(MailDraft)
        .where(MailDraft.inbound_message_id == msg.id)
        .values(inbound_message_id=None)
    )
    await db.delete(msg)
    await db.commit()
    return {"deleted": True}


# ── Drafts ────────────────────────────────────────────────────────────────


@router.post("/drafts/generate", response_model=GenerateDraftsResponse)
async def generate_drafts(
    payload: GenerateDraftsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count()).select_from(MailMessage).where(
            MailMessage.id.in_(payload.message_ids),
            MailMessage.user_id == user.id,
            MailMessage.direction == "inbound",
        )
    )
    if (result.scalar() or 0) != len(payload.message_ids):
        raise HTTPException(status_code=404, detail="One or more messages were not found.")

    run, draft_ids = await run_inbound_reply_agent(user.id, payload.message_ids, db)
    errors = []
    if run.status == "failed":
        errors.append(str((run.final_result or {}).get("error", "Generation failed.")))
    return GenerateDraftsResponse(
        run_id=run.id, status=run.status, draft_ids=draft_ids, errors=errors
    )


@router.post("/drafts", response_model=MailDraftResponse, status_code=201)
async def create_draft(
    payload: DraftCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hand-written reply from the editor (Reply button)."""
    if payload.inbound_message_id:
        await _get_message(payload.inbound_message_id, user.id, db)
    draft = MailDraft(
        user_id=user.id,
        inbound_message_id=payload.inbound_message_id,
        to_addr=payload.to_addr,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return _draft_response(draft)


@router.get("/drafts", response_model=list[MailDraftResponse])
async def list_drafts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MailDraft)
        .where(MailDraft.user_id == user.id, MailDraft.status == "draft")
        .order_by(MailDraft.updated_at.desc())
    )
    return [_draft_response(d) for d in result.scalars().all()]


@router.get("/drafts/{draft_id}", response_model=MailDraftResponse)
async def get_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return _draft_response(await _get_draft(draft_id, user.id, db))


@router.put("/drafts/{draft_id}", response_model=MailDraftResponse)
async def update_draft(
    draft_id: str,
    payload: DraftUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    draft = await _get_draft(draft_id, user.id, db)
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail="Only open drafts can be edited.")
    if payload.to_addr is not None:
        draft.to_addr = payload.to_addr
    if payload.subject is not None:
        draft.subject = payload.subject
    if payload.body is not None:
        draft.body = payload.body
    await db.commit()
    await db.refresh(draft)
    return _draft_response(draft)


@router.post("/drafts/{draft_id}/send", response_model=SendDraftResponse)
async def send_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    draft = await _get_draft(draft_id, user.id, db)
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail="Only open drafts can be sent.")
    try:
        sent = await send_reply(user.id, draft, db)
    except MailSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SendDraftResponse(draft_id=draft.id, sent_message_id=sent.id)


@router.post("/drafts/{draft_id}/discard", response_model=MailDraftResponse)
async def discard_draft(
    draft_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    draft = await _get_draft(draft_id, user.id, db)
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail="Only open drafts can be discarded.")
    draft.status = "discarded"
    await db.commit()
    await db.refresh(draft)
    return _draft_response(draft)
```

- [ ] **Step 2: Register the router in `main.py`** — extend the import line and add registration:

```python
from api.endpoints import chat, runs, logs, dashboard, calendar, pages, settings as settings_ep, knowledge as knowledge_ep, leads as leads_ep, mail as mail_ep
```
and after the leads router line:
```python
app.include_router(mail_ep.router, prefix="/api/mail", tags=["mail"])
```

- [ ] **Step 3: Boot + route smoke check**

Run: `python -c "from main import app; print([r.path for r in app.routes if '/api/mail' in r.path])"`
Expected: list containing `/api/mail/sync`, `/api/mail/messages`, `/api/mail/drafts/generate`, etc.

- [ ] **Step 4: Commit**

```
git add salesops-agent-backend/api/endpoints/mail.py salesops-agent-backend/main.py
git commit -m "feat(mail): /api/mail endpoints for folders, messages, drafts"
```

---

### Task 5: Frontend plumbing — types, proxy, sidebar

**Files:**
- Modify: `querysales-web/lib/types.ts` (append)
- Create: `querysales-web/app/api/mail/[...segments]/route.ts`
- Modify: `querysales-web/components/sidebar.tsx` (NAV_ITEMS)

- [ ] **Step 1: Append mail types to `lib/types.ts`**:

```ts
/* ── Mail workspace ────────────────────────────────────────────────── */

export type MailFolder = "inbox" | "sent" | "trash";

export interface MailMessageListItem {
  id: string;
  direction: "inbound" | "outbound";
  from_addr: string;
  to_addrs: string;
  subject: string;
  snippet: string;
  received_at: string;
  read: boolean;
  trashed: boolean;
}

export interface MailFolderCounts {
  inbox: number;
  sent: number;
  drafts: number;
  trash: number;
  inbox_unread: number;
}

export interface MailListResponse {
  messages: MailMessageListItem[];
  counts: MailFolderCounts;
}

export interface MailMessageDetail extends MailMessageListItem {
  body_text: string;
  in_reply_to_id: string | null;
  read_at: string | null;
}

export interface MailDraft {
  id: string;
  inbound_message_id: string | null;
  run_id: string | null;
  to_addr: string;
  subject: string;
  body: string;
  status: "draft" | "sent" | "discarded";
  sent_message_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SyncResult {
  synced: number;
  skipped_duplicates: number;
  errors: string[];
}

export interface GenerateDraftsResult {
  run_id: string;
  status: string;
  draft_ids: string[];
  errors: string[];
}
```

- [ ] **Step 2: Create the catch-all proxy `app/api/mail/[...segments]/route.ts`** — forwards method, query and JSON body, attaches the Bearer JWT server-side (Decision D4), and passes backend bodies (including `{detail}`) through untouched:

```ts
/**
 * /api/mail/* — catch-all proxy to the FastAPI mail router.
 * Attaches the session JWT server-side; backend error bodies pass through
 * so the client can surface `detail` verbatim.
 */

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { AUTH_COOKIE } from "@/lib/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

type Params = { params: Promise<{ segments: string[] }> };

async function forward(request: Request, { params }: Params) {
  const { segments } = await params;
  const target = new URL(`${API_URL}/api/mail/${segments.join("/")}`);
  target.search = new URL(request.url).search;

  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const res = await fetch(target.toString(), init);
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    console.error("[api/mail] proxy failed:", err instanceof Error ? err.message : err);
    return NextResponse.json(
      { detail: "The mail service is unreachable right now." },
      { status: 502 },
    );
  }
}

export async function GET(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function POST(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function PUT(request: Request, ctx: Params) {
  return forward(request, ctx);
}
export async function DELETE(request: Request, ctx: Params) {
  return forward(request, ctx);
}
```

- [ ] **Step 3: Add the Mail nav item in `components/sidebar.tsx`** — insert after the Dashboard entry in `NAV_ITEMS`:

```ts
  { href: "/mail", label: "Mail", icon: "✉️" },
```

- [ ] **Step 4: Commit**

```
git add querysales-web/lib/types.ts "querysales-web/app/api/mail/[...segments]/route.ts" querysales-web/components/sidebar.tsx
git commit -m "feat(mail): frontend types, catch-all proxy, sidebar nav"
```

---

### Task 6: Mail workspace UI

**Files:**
- Create: `querysales-web/app/(dashboard)/mail/components/folder-rail.tsx`
- Create: `querysales-web/app/(dashboard)/mail/components/message-list.tsx`
- Create: `querysales-web/app/(dashboard)/mail/components/message-view.tsx`
- Create: `querysales-web/app/(dashboard)/mail/components/draft-editor.tsx`
- Create: `querysales-web/app/(dashboard)/mail/mail-client.tsx`
- Create: `querysales-web/app/(dashboard)/mail/page.tsx`

Uses existing primitives: `components/ui/{button,card,input,textarea,label,states}` and `components/agent/analysis-timeline-client.tsx` (`AnalysisTimeline({ runId, onComplete })`) for generation progress. Read `components/ui/states.tsx` first and match its exact export/prop names if the build complains.

- [ ] **Step 1: `components/folder-rail.tsx`**:

```tsx
/** Folder rail — Inbox / Sent / Drafts / Trash with live counts. */

"use client";

import type { MailFolderCounts } from "@/lib/types";
import { cn } from "@/lib/utils";

export type MailView = "inbox" | "sent" | "drafts" | "trash";

const FOLDERS: { key: MailView; label: string }[] = [
  { key: "inbox", label: "Inbox" },
  { key: "sent", label: "Sent" },
  { key: "drafts", label: "Drafts" },
  { key: "trash", label: "Trash" },
];

export function FolderRail({
  active,
  counts,
  onSelect,
}: {
  active: MailView;
  counts: MailFolderCounts;
  onSelect: (view: MailView) => void;
}) {
  const countFor = (view: MailView) =>
    view === "inbox" ? counts.inbox_unread : counts[view];

  return (
    <nav className="w-40 shrink-0 space-y-1">
      {FOLDERS.map((f) => (
        <button
          key={f.key}
          onClick={() => onSelect(f.key)}
          className={cn(
            "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition",
            active === f.key
              ? "bg-primary-muted text-primary"
              : "text-text-secondary hover:bg-surface-highlight hover:text-text",
          )}
        >
          <span>{f.label}</span>
          {countFor(f.key) > 0 && (
            <span className="rounded-full bg-surface-highlight px-2 py-0.5 text-xs">
              {countFor(f.key)}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: `components/message-list.tsx`** — selectable rows + context toolbar:

```tsx
/** Selectable message list with folder-context toolbar. */

"use client";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import type { MailMessageListItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { MailView } from "./folder-rail";

export function MessageList({
  view,
  messages,
  selected,
  openId,
  loading,
  error,
  busy,
  onToggle,
  onOpen,
  onSync,
  onGenerate,
  onTrash,
  onRestore,
  onDeletePermanent,
  onMarkUnread,
}: {
  view: MailView;
  messages: MailMessageListItem[];
  selected: Set<string>;
  openId: string | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
  onSync: () => void;
  onGenerate: () => void;
  onTrash: () => void;
  onRestore: () => void;
  onDeletePermanent: () => void;
  onMarkUnread: () => void;
}) {
  if (loading) return <LoadingState message="Loading messages…" />;
  if (error) return <ErrorState message={error} />;
  if (messages.length === 0) {
    return view === "inbox" ? (
      <EmptyState
        title="No messages yet"
        description="Sync your inbox to pull in incoming email."
        action={
          <Button onClick={onSync} disabled={busy}>
            Sync inbox
          </Button>
        }
      />
    ) : (
      <EmptyState title="Nothing here" description="This folder is empty." />
    );
  }

  const anySelected = selected.size > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        {view === "inbox" && (
          <>
            <Button size="sm" variant="outline" onClick={onSync} disabled={busy}>
              Sync inbox
            </Button>
            <Button size="sm" onClick={onGenerate} disabled={!anySelected || busy}>
              Generate drafts
            </Button>
          </>
        )}
        {anySelected && view !== "trash" && (
          <>
            <Button size="sm" variant="outline" onClick={onTrash} disabled={busy}>
              Trash
            </Button>
            <Button size="sm" variant="outline" onClick={onMarkUnread} disabled={busy}>
              Mark unread
            </Button>
          </>
        )}
        {anySelected && view === "trash" && (
          <>
            <Button size="sm" variant="outline" onClick={onRestore} disabled={busy}>
              Restore
            </Button>
            <Button size="sm" variant="destructive" onClick={onDeletePermanent} disabled={busy}>
              Delete forever
            </Button>
          </>
        )}
      </div>

      <ul className="flex-1 divide-y divide-border overflow-y-auto">
        {messages.map((m) => (
          <li
            key={m.id}
            className={cn(
              "flex cursor-pointer items-start gap-3 px-3 py-3 transition hover:bg-surface-highlight",
              openId === m.id && "bg-surface-highlight",
            )}
            onClick={() => onOpen(m.id)}
          >
            <input
              type="checkbox"
              checked={selected.has(m.id)}
              onClick={(e) => e.stopPropagation()}
              onChange={() => onToggle(m.id)}
              className="mt-1 accent-[var(--primary)]"
              aria-label={`Select ${m.subject || m.id}`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className={cn("truncate text-sm", m.read ? "text-text-secondary" : "font-semibold text-text")}>
                  {m.direction === "inbound" ? m.from_addr : `To: ${m.to_addrs}`}
                </span>
                <span className="shrink-0 text-xs text-text-muted">
                  {new Date(m.received_at).toLocaleDateString()}
                </span>
              </div>
              <p className={cn("truncate text-sm", m.read ? "text-text-secondary" : "font-medium text-text")}>
                {m.subject || "(no subject)"}
              </p>
              <p className="truncate text-xs text-text-muted">{m.snippet}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: `components/message-view.tsx`** — full message pane:

```tsx
/** Full message pane with reply + folder actions. */

"use client";

import { Button } from "@/components/ui/button";
import type { MailMessageDetail } from "@/lib/types";

export function MessageView({
  message,
  busy,
  onReply,
  onTrash,
  onRestore,
  onDeletePermanent,
  onClose,
}: {
  message: MailMessageDetail;
  busy: boolean;
  onReply: () => void;
  onTrash: () => void;
  onRestore: () => void;
  onDeletePermanent: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <h2 className="truncate text-base font-semibold text-text">
          {message.subject || "(no subject)"}
        </h2>
        <div className="flex shrink-0 items-center gap-2">
          {!message.trashed && (
            <Button size="sm" onClick={onReply} disabled={busy}>
              Reply
            </Button>
          )}
          {!message.trashed ? (
            <Button size="sm" variant="outline" onClick={onTrash} disabled={busy}>
              Trash
            </Button>
          ) : (
            <>
              <Button size="sm" variant="outline" onClick={onRestore} disabled={busy}>
                Restore
              </Button>
              <Button size="sm" variant="destructive" onClick={onDeletePermanent} disabled={busy}>
                Delete forever
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
      <div className="space-y-1 border-b border-border px-4 py-3 text-sm">
        <p className="text-text">
          <span className="text-text-muted">From:</span> {message.from_addr}
        </p>
        <p className="text-text">
          <span className="text-text-muted">To:</span> {message.to_addrs}
        </p>
        <p className="text-text-muted">
          {new Date(message.received_at).toLocaleString()}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto whitespace-pre-wrap px-4 py-4 text-sm text-text">
        {message.body_text || "(empty message)"}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `components/draft-editor.tsx`** — editable draft with Save / Approve & send / Discard:

```tsx
/** Editable reply draft: Save, Approve & send, Discard. */

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { MailDraft } from "@/lib/types";

export function DraftEditor({
  draft,
  busy,
  onSave,
  onSend,
  onDiscard,
  onClose,
}: {
  draft: MailDraft;
  busy: boolean;
  onSave: (fields: { to_addr: string; subject: string; body: string }) => Promise<void>;
  onSend: () => Promise<void>;
  onDiscard: () => Promise<void>;
  onClose: () => void;
}) {
  const [toAddr, setToAddr] = useState(draft.to_addr);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-text">
          {draft.status === "sent" ? "Sent reply" : "Reply draft"}
        </h2>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <div className="space-y-1">
          <Label htmlFor="draft-to">To</Label>
          <Input id="draft-to" value={toAddr} onChange={(e) => setToAddr(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="draft-subject">Subject</Label>
          <Input id="draft-subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="draft-body">Message</Label>
          <Textarea
            id="draft-body"
            rows={14}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-error">{error}</p>}
      </div>

      {draft.status === "draft" && (
        <div className="flex items-center gap-2 border-t border-border px-4 py-3">
          <Button
            onClick={() => run(() => onSave({ to_addr: toAddr, subject, body }))}
            disabled={busy}
            variant="outline"
          >
            Save
          </Button>
          <Button onClick={() => run(onSend)} disabled={busy}>
            Approve &amp; send
          </Button>
          <Button onClick={() => run(onDiscard)} disabled={busy} variant="ghost">
            Discard
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: `mail-client.tsx`** — workspace state machine (folder switching, selection, sync, generate + timeline, draft lifecycle). Client-side `mailFetch` surfaces backend `detail` and redirects on 401:

```tsx
/** Gmail-style Mail workspace: folders, list, detail, draft editor. */

"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { AnalysisTimeline } from "@/components/agent/analysis-timeline-client";
import { Card } from "@/components/ui/card";
import type {
  GenerateDraftsResult,
  MailDraft,
  MailFolderCounts,
  MailListResponse,
  MailMessageDetail,
  MailMessageListItem,
  SyncResult,
} from "@/lib/types";
import { DraftEditor } from "./components/draft-editor";
import { FolderRail, type MailView } from "./components/folder-rail";
import { MessageList } from "./components/message-list";
import { MessageView } from "./components/message-view";

async function mailFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/mail${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as
      | { detail?: string | { message?: string }[] }
      | null;
    const detail = Array.isArray(body?.detail)
      ? body?.detail.map((e) => e.message).join(", ")
      : body?.detail;
    throw new Error(detail ?? `Request failed (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export function MailClient({ initial }: { initial: MailListResponse }) {
  const router = useRouter();
  const [view, setView] = useState<MailView>("inbox");
  const [messages, setMessages] = useState<MailMessageListItem[]>(initial.messages);
  const [counts, setCounts] = useState<MailFolderCounts>(initial.counts);
  const [drafts, setDrafts] = useState<MailDraft[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openMessage, setOpenMessage] = useState<MailMessageDetail | null>(null);
  const [openDraft, setOpenDraft] = useState<MailDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatingRunId, setGeneratingRunId] = useState<string | null>(null);

  const loadFolder = useCallback(async (next: MailView) => {
    setView(next);
    setSelected(new Set());
    setOpenMessage(null);
    setOpenDraft(null);
    setError(null);
    setLoading(true);
    try {
      if (next === "drafts") {
        setDrafts(await mailFetch<MailDraft[]>("/drafts"));
      } else {
        const res = await mailFetch<MailListResponse>(`/messages?folder=${next}`);
        setMessages(res.messages);
        setCounts(res.counts);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load folder.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleSync() {
    setBusy(true);
    setError(null);
    try {
      const res = await mailFetch<SyncResult>("/sync", { method: "POST" });
      await loadFolder(view === "drafts" ? "inbox" : view);
      if (res.errors.length > 0) {
        setError(`Synced ${res.synced} message(s) with issues: ${res.errors.join(" ")}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const res = await mailFetch<GenerateDraftsResult>("/drafts/generate", {
        method: "POST",
        body: JSON.stringify({ message_ids: [...selected] }),
      });
      if (res.status === "failed") {
        setError(res.errors[0] ?? "Draft generation failed.");
      } else {
        setGeneratingRunId(res.run_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function messageAction(path: string, method: string) {
    setBusy(true);
    setError(null);
    try {
      await mailFetch<unknown>(path, { method });
      await loadFolder(view);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function bulkAction(pathFor: (id: string) => string, method: string) {
    setBusy(true);
    setError(null);
    try {
      await Promise.all(
        [...selected].map((id) => mailFetch<unknown>(pathFor(id), { method })),
      );
      await loadFolder(view);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openMessageDetail(id: string) {
    setError(null);
    try {
      const detail = await mailFetch<MailMessageDetail>(`/messages/${id}`);
      setOpenDraft(null);
      setOpenMessage(detail);
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, read: true } : m)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open message.");
    }
  }

  function replyTo(message: MailMessageDetail) {
    setOpenDraft({
      id: "",
      inbound_message_id: message.id,
      run_id: null,
      to_addr: message.from_addr,
      subject: message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`,
      body: `\n\n---\nOn ${new Date(message.received_at).toLocaleString()}, ${message.from_addr} wrote:\n${message.body_text}`,
      status: "draft",
      sent_message_id: null,
      created_at: "",
      updated_at: "",
    });
  }

  async function saveDraft(fields: { to_addr: string; subject: string; body: string }) {
    if (!openDraft) return;
    if (openDraft.id === "") {
      const created = await mailFetch<MailDraft>("/drafts", {
        method: "POST",
        body: JSON.stringify({ ...fields, inbound_message_id: openDraft.inbound_message_id }),
      });
      setOpenDraft(created);
      return;
    }
    const updated = await mailFetch<MailDraft>(`/drafts/${openDraft.id}`, {
      method: "PUT",
      body: JSON.stringify(fields),
    });
    setOpenDraft(updated);
  }

  async function sendDraft() {
    if (!openDraft) return;
    let draftId = openDraft.id;
    if (draftId === "") {
      const created = await mailFetch<MailDraft>("/drafts", {
        method: "POST",
        body: JSON.stringify({
          to_addr: openDraft.to_addr,
          subject: openDraft.subject,
          body: openDraft.body,
          inbound_message_id: openDraft.inbound_message_id,
        }),
      });
      draftId = created.id;
    }
    await mailFetch<unknown>(`/drafts/${draftId}/send`, { method: "POST" });
    setOpenDraft(null);
    router.refresh();
    await loadFolder("sent");
  }

  async function discardDraft() {
    if (!openDraft || openDraft.id === "") return;
    await mailFetch<MailDraft>(`/drafts/${openDraft.id}/discard`, { method: "POST" });
    setOpenDraft(null);
    await loadFolder(view);
  }

  const listItems: MailMessageListItem[] =
    view === "drafts"
      ? drafts.map((d) => ({
          id: d.id,
          direction: "outbound" as const,
          from_addr: "Draft",
          to_addrs: d.to_addr,
          subject: d.subject,
          snippet: d.body.slice(0, 200),
          received_at: d.updated_at,
          read: true,
          trashed: false,
        }))
      : messages;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-text">Mail</h1>

      {generatingRunId && (
        <Card className="p-4">
          <AnalysisTimeline
            runId={generatingRunId}
            onComplete={() => {
              setGeneratingRunId(null);
              void loadFolder("drafts");
            }}
          />
        </Card>
      )}

      <div className="flex gap-4">
        <FolderRail active={view} counts={counts} onSelect={(v) => void loadFolder(v)} />

        <Card className="h-[calc(100vh-220px)] min-w-0 flex-1 p-0">
          <MessageList
            view={view}
            messages={listItems}
            selected={selected}
            openId={openMessage?.id ?? openDraft?.id ?? null}
            loading={loading}
            error={error}
            busy={busy}
            onToggle={(id) =>
              setSelected((prev) => {
                const next = new Set(prev);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            onOpen={(id) => {
              if (view === "drafts") {
                const draft = drafts.find((d) => d.id === id);
                if (draft) {
                  setOpenMessage(null);
                  setOpenDraft(draft);
                }
              } else {
                void openMessageDetail(id);
              }
            }}
            onSync={() => void handleSync()}
            onGenerate={() => void handleGenerate()}
            onTrash={() => void bulkAction((id) => `/messages/${id}/trash`, "POST")}
            onRestore={() => void bulkAction((id) => `/messages/${id}/restore`, "POST")}
            onDeletePermanent={() => void bulkAction((id) => `/messages/${id}`, "DELETE")}
            onMarkUnread={() => void bulkAction((id) => `/messages/${id}/unread`, "POST")}
          />
        </Card>

        {(openMessage || openDraft) && (
          <Card className="h-[calc(100vh-220px)] w-[42%] shrink-0 p-0">
            {openDraft ? (
              <DraftEditor
                draft={openDraft}
                busy={busy}
                onSave={saveDraft}
                onSend={sendDraft}
                onDiscard={discardDraft}
                onClose={() => setOpenDraft(null)}
              />
            ) : openMessage ? (
              <MessageView
                message={openMessage}
                busy={busy}
                onReply={() => replyTo(openMessage)}
                onTrash={() => void messageAction(`/messages/${openMessage.id}/trash`, "POST")}
                onRestore={() => void messageAction(`/messages/${openMessage.id}/restore`, "POST")}
                onDeletePermanent={() => void messageAction(`/messages/${openMessage.id}`, "DELETE")}
                onClose={() => setOpenMessage(null)}
              />
            ) : null}
          </Card>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: `page.tsx`** — server component seeds the inbox:

```tsx
/** Mail workspace — server component seeds the initial inbox view. */

import { apiGet } from "@/lib/api-client";
import type { MailListResponse } from "@/lib/types";
import { MailClient } from "./mail-client";

export const dynamic = "force-dynamic";

export default async function MailPage() {
  let initial: MailListResponse = {
    messages: [],
    counts: { inbox: 0, sent: 0, drafts: 0, trash: 0, inbox_unread: 0 },
  };
  try {
    initial = await apiGet<MailListResponse>("/api/mail/messages", { folder: "inbox" });
  } catch {
    /* client shows error/empty states and can retry via Sync */
  }
  return <MailClient initial={initial} />;
}
```

- [ ] **Step 7: Type gate**

Run (from `querysales-web/`): `npm run build`
Expected: zero errors. If `components/ui/states.tsx` or `cn` exports differ, match them exactly (read those files first if the build complains).

- [ ] **Step 8: Commit**

```
git add "querysales-web/app/(dashboard)/mail"
git commit -m "feat(mail): Gmail-style workspace UI (folders, list, view, editor)"
```

---

### Task 7: E2E verification, isolation, docs

**Files:**
- Modify: `AGENTS.md` (§7 memory)
- Create: `docs/summery/feature-inbound-email-mail-workspace.md`

- [ ] **Step 1: Boot both servers** (background): backend `uvicorn main:app --reload --port 8000` from `salesops-agent-backend/`; frontend `npm run dev` from `querysales-web/` (port 3001).

- [ ] **Step 2: Authenticated API walkthrough** (httpx script, PowerShell-safe): login as `demo@querysales.demo` / `Demo1234!` via `POST :3001/api/auth/login`, capture the `qs_session` cookie, then against `:3001` with that cookie:
  1. `POST /api/mail/sync` → 200 `{synced, skipped_duplicates, errors}` if email config exists, else 400/502 with an actionable `detail` (record which).
  2. `GET /api/mail/messages?folder=inbox` → 200 with `counts`.
  3. If messages exist: `POST /api/mail/drafts/generate {message_ids:[first]}` → 200 with `run_id`; poll `GET /api/runs/{run_id}/events` until COMPLETE/ERROR; `GET /api/mail/drafts` contains the draft.
  4. `PUT /api/mail/drafts/{id}` editing body → 200 reflects edit.
  5. `POST /api/mail/drafts/{id}/send` → 200 + Sent folder contains the copy (or clean 502 if SMTP creds invalid — record).
  6. Trash → appears in `folder=trash`; restore → back in inbox; trash again + `DELETE` → gone.
  Expected: every step returns the documented status; no 500s; no secrets in any response.

- [ ] **Step 3: Isolation check** — with a second user's cookie (e.g. `probe-test-9x7@querysales.demo` if it still exists): `GET /api/mail/messages/{userA_message_id}` → 404; `GET /api/mail/drafts/{userA_draft_id}` → 404.

- [ ] **Step 4: UI pass** — browser: `/mail` shows rail + inbox; select → Generate drafts shows the run timeline; Drafts editor edits + saves; all four folders render; `npm run build` still zero errors.

- [ ] **Step 5: Docs** — append to `AGENTS.md` §7 a memory entry (IMAP derived from SMTP; mail_messages/mail_drafts tables; /api/mail router; /mail workspace; sync is read-only against the remote mailbox) and write `docs/summery/feature-inbound-email-mail-workspace.md` from `docs/summery/_TEMPLATE.md` (files changed with one-line why, verification commands + actual results, deferrals: attachments, scheduled polling, provider-side Drafts).

- [ ] **Step 6: Commit**

```
git add AGENTS.md docs/summery/feature-inbound-email-mail-workspace.md
git commit -m "docs: inbound email feature summary + project memory"
```
