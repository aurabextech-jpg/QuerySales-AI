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
