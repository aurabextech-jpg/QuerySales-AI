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
