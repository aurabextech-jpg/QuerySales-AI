"""Autonomous sales agent (plan §12, §34).

A single agent that decides when to retrieve knowledge, reason about a lead,
plan actions, and call tools. Uses the OpenAI Agents SDK with structured output.

System prompt encodes: OBSERVE → RETRIEVE → REASON → PLAN → ACT → RESULT.
The agent MUST call search_knowledge before qualifying any lead.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from agents import Agent, Runner
from agents.tracing import set_trace_processors

from agent_core.events import emit, OBSERVE, RETRIEVE, REASON, PLAN, TOOL_CALL, COMPLETE, ERROR
from agent_core.model_factory import build_model
from agent_core.sales_tools import (
    SalesAgentContext,
    search_knowledge_tool,
    get_lead_tool,
    update_lead_tool,
    draft_outreach_tool,
)
from agent_core.tracing import DatabaseTracingProcessor, flush_pending_writes
from core.user_config import (
    ConfigurationMissing,
    ResolvedEmbeddingConfig,
    ResolvedLLMConfig,
    resolve_embedding_config,
    resolve_llm_config,
)
from db.models import Lead, WorkflowRun

logger = logging.getLogger(__name__)

# Ensure tracing is registered (idempotent)
set_trace_processors([DatabaseTracingProcessor()])


# ── Structured output (plan §14) ──────────────────────────────────────────


class OutreachOutput(BaseModel):
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Personalised email body")


class SalesAnalysisOutput(BaseModel):
    lead_score: int = Field(ge=0, le=100, description="Lead quality score 0-100")
    qualification: str = Field(
        description="One of: Qualified, Nurture, Disqualified"
    )
    reasoning: str = Field(
        description="Concise business rationale for the qualification (not internal chain-of-thought)"
    )
    pain_points: list[str] = Field(
        default_factory=list,
        description="Identified pain points or challenges",
    )
    matched_knowledge: list[str] = Field(
        default_factory=list,
        description="Summaries of knowledge articles that were relevant",
    )
    recommended_action: str = Field(
        description="The recommended next action for the sales rep",
    )
    outreach: OutreachOutput = Field(
        description="A personalised outreach email draft",
    )


# ── System prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are QuerySales AI, an autonomous sales analyst. Your job is to analyse a \
sales lead and produce a qualification, score, and personalised outreach.

## Your process

Follow this loop strictly:

1. **OBSERVE** — Read the lead details provided below.
2. **RETRIEVE** — Call `search_knowledge_tool` with queries relevant to the \
   lead's industry, company, or pain points. You MUST search the knowledge base \
   before qualifying the lead. Try 2-3 different queries to get broad coverage.
3. **REASON** — Based on the lead data AND the knowledge you retrieved, assess:
   - How well does our product fit their industry/needs?
   - What pain points can we address?
   - What is the likely budget/decision complexity?
4. **PLAN** — Decide the qualification (Qualified/Nurture/Disqualified), score \
   (0-100), and the recommended next action.
5. **ACT** — Call `update_lead_tool` with your assessment (status, score, \
   pain_points, notes). Then call `draft_outreach_tool` with a personalised email.
6. **RESULT** — Return your structured analysis.

## Rules
- ALWAYS search the knowledge base before qualifying. Never skip RETRIEVE.
- The outreach must reference specific details about the lead's company/industry.
- Use `get_lead_tool` first if you need more details about the lead.
- Notes should be a concise summary of your reasoning (2-3 sentences).
- Never fabricate information not present in the lead data or knowledge base.
"""


# ── Agent builder ─────────────────────────────────────────────────────────


def _build_agent(model) -> Agent:
    """Build the sales analysis agent with tools and structured output."""
    try:
        return Agent(
            name="SalesAnalyst",
            instructions=SYSTEM_PROMPT,
            model=model,
            tools=[
                search_knowledge_tool,
                get_lead_tool,
                update_lead_tool,
                draft_outreach_tool,
            ],
            output_type=SalesAnalysisOutput,
        )
    except (TypeError, ValueError):
        # Some providers don't support structured output via output_type.
        # Fall back to plain text with JSON parsing.
        logger.warning(
            "Structured output not supported by provider, falling back to JSON prompt"
        )
        return Agent(
            name="SalesAnalyst",
            instructions=SYSTEM_PROMPT + "\n\nReturn your analysis as a JSON object matching this schema: "
            "{lead_score, qualification, reasoning, pain_points, matched_knowledge, recommended_action, outreach: {subject, body}}",
            model=model,
            tools=[
                search_knowledge_tool,
                get_lead_tool,
                update_lead_tool,
                draft_outreach_tool,
            ],
        )


# ── Run function ──────────────────────────────────────────────────────────


async def run_sales_agent(
    lead_id: str,
    user_id: str,
    db: AsyncSession,
) -> WorkflowRun:
    """Run the autonomous sales agent on a lead.

    Resolves per-user config, builds the model, runs the agent, persists
    the result and emits semantic events.
    """
    # ── 1. Resolve config ─────────────────────────────────────────────
    try:
        llm_cfg = await resolve_llm_config(user_id, db)
        embed_cfg = await resolve_embedding_config(user_id, db)
    except ConfigurationMissing as exc:
        # Create a failed run immediately
        run = WorkflowRun(
            user_id=user_id,
            lead_id=lead_id,
            workflow_type="lead_analysis",
            status="failed",
            final_result={"error": exc.message},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        await emit(
            db,
            run_id=run.id,
            user_id=user_id,
            phase=ERROR,
            title="Configuration missing",
            detail=exc.message,
        )
        return run

    # ── 2. Load the lead ──────────────────────────────────────────────
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == user_id)
    )
    lead = result.scalars().first()
    if not lead:
        raise ValueError(f"Lead {lead_id} not found for user {user_id}")

    # ── 3. Create the run ─────────────────────────────────────────────
    run = WorkflowRun(
        user_id=user_id,
        lead_id=lead_id,
        workflow_type="lead_analysis",
        status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # ── 4. Emit OBSERVE ───────────────────────────────────────────────
    await emit(
        db,
        run_id=run.id,
        user_id=user_id,
        phase=OBSERVE,
        title="Starting lead analysis",
        detail=f"Analyzing lead: {lead.name or lead.company}",
        payload={
            "lead_id": lead_id,
            "company": lead.company,
            "industry": lead.industry,
        },
    )

    # ── 5. Build and run agent ────────────────────────────────────────
    try:
        model = build_model(llm_cfg)
        agent = _build_agent(model)

        ctx = SalesAgentContext(
            run_id=run.id,
            user_id=user_id,
            lead_id=lead_id,
            db=db,
            embed_cfg=embed_cfg,
        )

        user_message = (
            f"Analyse this lead and provide a qualification, score, and personalised outreach.\n\n"
            f"Lead ID: {lead.id}\n"
            f"Name: {lead.name or 'N/A'}\n"
            f"Company: {lead.company}\n"
            f"Email: {lead.email or 'N/A'}\n"
            f"Industry: {lead.industry or 'N/A'}\n"
            f"Website: {lead.website or 'N/A'}\n"
            f"Current Status: {lead.status}\n"
            f"Notes: {lead.notes or 'None'}\n"
        )

        await emit(
            db,
            run_id=run.id,
            user_id=user_id,
            phase=REASON,
            title="Agent reasoning started",
            detail=f"Model: {llm_cfg.model}, Provider: {llm_cfg.provider_name}",
        )

        agent_result = await Runner.run(
            agent,
            input=user_message,
            context=ctx,
        )

        # ── 6. Parse output ───────────────────────────────────────────
        final_result = _parse_output(agent_result)

        await emit(
            db,
            run_id=run.id,
            user_id=user_id,
            phase=COMPLETE,
            title="Analysis complete",
            detail=f"Qualification: {final_result.get('qualification', 'N/A')}, "
                   f"Score: {final_result.get('lead_score', 'N/A')}",
            payload={"result": final_result},
        )

        run.status = "completed"
        run.final_result = final_result
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        # Flush tracing writes
        await flush_pending_writes()

        logger.info(
            "Sales agent completed: run=%s lead=%s qualification=%s score=%s",
            run.id[:8], lead_id[:8],
            final_result.get("qualification"),
            final_result.get("lead_score"),
        )

    except Exception as exc:
        logger.error(
            "Sales agent failed: run=%s lead=%s: %s",
            run.id[:8], lead_id[:8], exc,
            exc_info=True,
        )

        run.status = "failed"
        run.final_result = {"error": "Analysis failed. Please try again."}
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        await emit(
            db,
            run_id=run.id,
            user_id=user_id,
            phase=ERROR,
            title="Analysis failed",
            detail="An unexpected error occurred during analysis. Please try again.",
        )

        await flush_pending_writes()

    await db.refresh(run)
    return run


def _parse_output(agent_result) -> dict:
    """Parse the agent's output into a dict.

    Handles both structured output (Pydantic model) and plain text with
    JSON parsing fallback.
    """
    output = agent_result.final_output

    # Structured output (Pydantic model)
    if isinstance(output, SalesAnalysisOutput):
        return output.model_dump()

    # String output — try JSON parse
    if isinstance(output, str):
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {
                "reasoning": output,
                "qualification": "Unknown",
                "lead_score": 50,
            }

    # Fallback
    return {
        "reasoning": str(output) if output else "No output produced",
        "qualification": "Unknown",
        "lead_score": 50,
    }
