"""Dashboard endpoint — the KPI tiles and pipeline breakdown.

GET /api/dashboard/stats

Every figure comes from this app's own user-scoped tables. ERPNext is not
consulted here: leads live in our Postgres (Decision D5), so an optional
integration must never sit in the critical path of the landing page.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from db.models import (
    User,
    WorkflowRun,
    ToolCallLog,
    Lead,
    KnowledgeDocument,
    OutreachDraft,
)
from db.session import get_db
from core.user_config import resolve_integration_config
from mcp_tools.erpnext import analyze_crm_data, AnalyzeCrmInput

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response models ──────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    """The five KPI tiles plus the status breakdown behind them.

    Mirrors ``DashboardStats`` in querysales-web/lib/types.ts — the dashboard
    reads these keys directly, so renaming one blanks a tile.
    """

    total_leads: int = 0
    qualified_leads: int = 0
    outreach_sent: int = 0
    active_runs: int = 0
    knowledge_documents: int = 0
    # Lead status → count, e.g. {"New": 3, "Qualified": 2}
    pipeline: dict[str, int] = Field(default_factory=dict)


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KPI tiles for the authenticated user, all from user-scoped local tables."""
    try:
        pipeline_result = await db.execute(
            select(Lead.status, func.count(Lead.id))
            .where(Lead.user_id == current_user.id)
            .group_by(Lead.status)
        )
        pipeline = {status: count for status, count in pipeline_result.all()}

        sent_result = await db.execute(
            select(func.count(OutreachDraft.id)).where(
                OutreachDraft.user_id == current_user.id,
                OutreachDraft.status == "sent",
            )
        )

        active_result = await db.execute(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.user_id == current_user.id,
                WorkflowRun.status == "running",
            )
        )

        docs_result = await db.execute(
            select(func.count(KnowledgeDocument.id))
            .where(KnowledgeDocument.user_id == current_user.id)
        )

        return DashboardStatsResponse(
            total_leads=sum(pipeline.values()),
            qualified_leads=pipeline.get("Qualified", 0),
            outreach_sent=sent_result.scalar() or 0,
            active_runs=active_result.scalar() or 0,
            knowledge_documents=docs_result.scalar() or 0,
            pipeline=pipeline,
        )
    except Exception as exc:
        logger.error(
            "Dashboard stats failed for user=%s: %s",
            current_user.id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve dashboard stats.",
        )



@router.get("/leads")
async def get_paginated_leads(
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated leads from ERPNext with optional status filtering."""
    try:
        filters = {}
        if status:
            filters["status"] = status
            
        input_data = AnalyzeCrmInput(
            doctype="Lead",
            fields=["name", "lead_name", "status", "source", "creation", "email_id", "mobile_no"],
            limit=limit,
            limit_start=offset,
            order_by="creation desc",
            filters=filters if filters else None,
        )
        
        erp_creds = await resolve_integration_config(current_user.id, "erpnext", db)
        response = await analyze_crm_data(input_data, erp_creds)
        if response.get("status") == "error":
            raise HTTPException(status_code=502, detail=response.get("message"))
            
        records = response.get("data", [])
        return {
            "status": "success",
            "limit": limit,
            "offset": offset,
            "total_returned": len(records),
            "data": records
        }
    except Exception as exc:
        logger.error("Failed to retrieve paginated leads: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve leads")


# ── Legacy per-run outcome (kept for backward compat) ────────────────────

class OutcomeMetrics(BaseModel):
    leadsFound: int = 0
    duplicatesPrevented: int = 0
    meetingsScheduled: int = 0
    todosCreated: int = 0


class OutcomeResponse(BaseModel):
    run_id: str
    metrics: OutcomeMetrics


@router.get("/{run_id}/outcome", response_model=OutcomeResponse)
async def get_outcome_metrics(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute outcome metrics from tool-call logs for a workflow run."""
    try:
        # Verify ownership
        run_result = await db.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id,
                WorkflowRun.user_id == current_user.id,
            )
        )
        run = run_result.scalars().first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Fetch all tool-call logs for this run
        tool_result = await db.execute(
            select(ToolCallLog).where(ToolCallLog.run_id == run_id)
        )
        tool_logs = tool_result.scalars().all()

        leads_found = 0
        duplicates_prevented = 0
        meetings_scheduled = 0
        todos_created = 0

        for log in tool_logs:
            name = log.tool_name or ""
            output = log.output_data if isinstance(log.output_data, dict) else {}
            is_success = not log.error and output.get("status") != "error"

            if not is_success:
                continue

            if name == "search_businesses":
                data = output.get("data", output.get("results", []))
                if isinstance(data, list):
                    leads_found += len(data)
                elif isinstance(data, dict):
                    leads_found += data.get("total", 1)

            elif name == "create_erpnext_lead":
                todos_created += 1

            elif name == "analyze_crm_data":
                summary = output.get("summary", {})
                if isinstance(summary, dict):
                    duplicates_prevented += summary.get("duplicates_found", 0)

            elif name == "create_event":
                meetings_scheduled += 1

        return OutcomeResponse(
            run_id=run_id,
            metrics=OutcomeMetrics(
                leadsFound=leads_found,
                duplicatesPrevented=duplicates_prevented,
                meetingsScheduled=meetings_scheduled,
                todosCreated=todos_created,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "get_outcome_metrics failed for run_id=%s: %s", run_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve outcome metrics.",
        )
