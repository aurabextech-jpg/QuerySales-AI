"""Sales agent tools (plan §13).

Four core tools the autonomous agent can call:
  1. search_knowledge — RAG retrieval (the critical one)
  2. get_lead — read a lead's details
  3. update_lead — write lead status/score/notes
  4. draft_outreach — persist an outreach draft (never sends)

All tools are user-scoped: they operate only on the authenticated user's data.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from agents import RunContextWrapper, function_tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import Lead, OutreachDraft
from services.knowledge.search import search_knowledge
from services.knowledge.embed import embed_texts

logger = logging.getLogger(__name__)


class SalesAgentContext:
    """Context threaded through every tool call via RunContextWrapper."""

    def __init__(
        self,
        run_id: str,
        user_id: str,
        lead_id: str,
        db: AsyncSession,
        embed_cfg,
    ):
        self.run_id = run_id
        self.user_id = user_id
        self.lead_id = lead_id
        self.db = db
        self.embed_cfg = embed_cfg


# ── Tool 1: search_knowledge (plan §11) ───────────────────────────────────


@function_tool
async def search_knowledge_tool(
    ctx: RunContextWrapper[SalesAgentContext],
    query: str,
    top_k: int = 5,
) -> str:
    """Search the company knowledge base for relevant information.

    Use this tool to find product details, pricing, case studies, FAQs,
    or any company information that helps qualify or engage the lead.

    Args:
        query: What to search for (e.g. "inventory management pricing")
        top_k: Maximum number of results to return (default 5)
    """
    cfg = ctx.context
    logger.info(
        "search_knowledge called: run=%s user=%s query='%s'",
        cfg.run_id[:8], cfg.user_id[:8], query[:80],
    )

    # Embed the query
    embeddings = await embed_texts([query], cfg.embed_cfg)
    query_vec = embeddings[0]

    # Search (user_id filter is inside the SQL)
    results = await search_knowledge(
        query_embedding=query_vec,
        user_id=cfg.user_id,
        db=cfg.db,
        top_k=min(top_k, 10),
    )

    if not results:
        return "No relevant knowledge found for this query."

    output_parts = []
    for i, r in enumerate(results, 1):
        source = r.document_title or r.document_filename
        output_parts.append(
            f"[{i}] (similarity: {r.similarity:.3f}, source: {source})\n{r.content}"
        )

    return "\n\n---\n\n".join(output_parts)


# ── Tool 2: get_lead ──────────────────────────────────────────────────────


@function_tool
async def get_lead_tool(
    ctx: RunContextWrapper[SalesAgentContext],
    lead_id: str,
) -> str:
    """Get the full details of a specific lead.

    Args:
        lead_id: The UUID of the lead to retrieve
    """
    cfg = ctx.context
    result = await cfg.db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == cfg.user_id)
    )
    lead = result.scalars().first()

    if not lead:
        return f"Lead {lead_id} not found."

    return json.dumps({
        "id": lead.id,
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "industry": lead.industry,
        "website": lead.website,
        "status": lead.status,
        "score": lead.score,
        "pain_points": lead.pain_points,
        "notes": lead.notes,
    })


# ── Tool 3: update_lead ───────────────────────────────────────────────────


@function_tool
async def update_lead_tool(
    ctx: RunContextWrapper[SalesAgentContext],
    lead_id: str,
    status: Optional[str] = None,
    score: Optional[int] = None,
    pain_points: Optional[list[str]] = None,
    notes: Optional[str] = None,
) -> str:
    """Update a lead's qualification details.

    Use this after analyzing the lead and matching knowledge. At minimum,
    update the status and score based on your qualification assessment.

    Args:
        lead_id: The UUID of the lead to update
        status: New status (New, Analyzing, Qualified, Nurture, Disqualified, Contacted)
        score: Lead quality score 0-100
        pain_points: List of identified pain points or challenges
        notes: Analysis notes or reasoning summary
    """
    cfg = ctx.context
    result = await cfg.db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == cfg.user_id)
    )
    lead = result.scalars().first()

    if not lead:
        return f"Lead {lead_id} not found or not owned by you."

    if status is not None:
        lead.status = status
    if score is not None:
        lead.score = max(0, min(100, score))
    if pain_points is not None:
        lead.pain_points = pain_points
    if notes is not None:
        lead.notes = notes

    await cfg.db.commit()

    logger.info(
        "update_lead: run=%s lead=%s status=%s score=%s",
        cfg.run_id[:8], lead_id[:8], status, score,
    )
    return f"Lead updated: status={lead.status}, score={lead.score}"


# ── Tool 4: draft_outreach ────────────────────────────────────────────────


@function_tool
async def draft_outreach_tool(
    ctx: RunContextWrapper[SalesAgentContext],
    lead_id: str,
    subject: str,
    body: str,
) -> str:
    """Create a personalised outreach email draft for a lead.

    The draft is saved but NEVER sent automatically. A human must
    review and approve it before sending.

    Args:
        lead_id: The UUID of the lead this outreach targets
        subject: Email subject line
        body: Email body (plain text, personalised to the lead)
    """
    cfg = ctx.context

    # Verify lead ownership
    result = await cfg.db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == cfg.user_id)
    )
    lead = result.scalars().first()
    if not lead:
        return f"Lead {lead_id} not found or not owned by you."

    draft = OutreachDraft(
        user_id=cfg.user_id,
        lead_id=lead_id,
        run_id=cfg.run_id,
        subject=subject,
        body=body,
    )
    cfg.db.add(draft)
    await cfg.db.commit()

    logger.info(
        "draft_outreach: run=%s lead=%s subject='%s'",
        cfg.run_id[:8], lead_id[:8], subject[:60],
    )
    return f"Outreach draft created (id: {draft.id}). Status: draft — requires human approval before sending."


# ── Tool list for the agent ───────────────────────────────────────────────

ALL_TOOLS = [
    search_knowledge_tool,
    get_lead_tool,
    update_lead_tool,
    draft_outreach_tool,
]
