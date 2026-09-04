"""Dashboard endpoint — real-time stats from ERPNext + local DB metrics.

GET /api/dashboard/stats

Returns:
  - CRM pipeline breakdown (from ERPNext Lead API)
  - Agent usage metrics (from local workflow_runs / audit_traces)
  - Recent activity (from local chat_messages + tool_call_logs)
"""

import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import get_current_user
from db.models import (
    User,
    WorkflowRun,
    AuditTrace,
    ToolCallLog,
    ChatMessageLog,
)
from db.session import get_db
from mcp_tools.erpnext import analyze_crm_data, AnalyzeCrmInput

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response models ──────────────────────────────────────────────────────

class PipelineStats(BaseModel):
    """Lead pipeline breakdown from ERPNext."""
    total_leads: int = 0
    open: int = 0
    replied: int = 0
    opportunity: int = 0
    converted: int = 0
    do_not_contact: int = 0


class AgentUsageStats(BaseModel):
    """Usage metrics from local DB."""
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    total_messages: int = 0
    total_tool_calls: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0


class RecentActivity(BaseModel):
    """Recent item for the activity feed."""
    type: str  # "message" | "tool_call" | "run"
    description: str
    timestamp: str


class DashboardResponse(BaseModel):
    pipeline: PipelineStats
    usage: AgentUsageStats
    recent_activity: list[RecentActivity]
    categorized_leads: dict = {}
    raw_leads: list = []


# ── ERPNext helpers ──────────────────────────────────────────────────────

async def _fetch_erpnext_pipeline() -> PipelineStats:
    """Fetch lead status counts directly from ERPNext API."""
    if not settings.ERPNEXT_BASE_URL or not settings.ERPNEXT_API_TOKEN:
        logger.warning("ERPNext not configured — returning empty pipeline stats.")
        return PipelineStats()

    headers = {"Authorization": f"token {settings.ERPNEXT_API_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch all leads with status field
            response = await client.get(
                f"{settings.ERPNEXT_BASE_URL}/api/resource/Lead",
                params={
                    "fields": '["name","status"]',
                    "limit_page_length": 0,  # 0 = all records
                },
                headers=headers,
            )
            response.raise_for_status()
            leads = response.json().get("data", [])

        # Count by status
        status_map: dict[str, int] = {}
        for lead in leads:
            status = lead.get("status", "Open")
            status_map[status] = status_map.get(status, 0) + 1

        return PipelineStats(
            total_leads=len(leads),
            open=status_map.get("Open", 0),
            replied=status_map.get("Replied", 0),
            opportunity=status_map.get("Opportunity", 0),
            converted=status_map.get("Converted", 0),
            do_not_contact=status_map.get("Do Not Contact", 0),
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "ERPNext API error %d: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return PipelineStats()
    except Exception as exc:
        logger.error("ERPNext pipeline fetch failed: %s", exc)
        return PipelineStats()

async def _fetch_recent_leads() -> tuple[dict, list]:
    """Fetch recent leads and categorize them."""
    try:
        input_data = AnalyzeCrmInput(
            doctype="Lead",
            fields=["name", "lead_name", "status", "source", "creation", "email_id", "mobile_no"],
            limit=3,
            order_by="creation desc"
        )
        response = await analyze_crm_data(input_data)
        if response.get("status") == "error":
            return {}, []
            
        records = response.get("data", [])
        
        categorized = {
            "Open": [],
            "Replied": [],
            "Opportunity": [],
            "Converted": [],
            "Do Not Contact": []
        }
        
        for record in records:
            status = record.get("status", "Open")
            if status in categorized:
                categorized[status].append(record)
            else:
                categorized["Open"].append(record)
                
        return categorized, records
    except Exception as exc:
        logger.error("ERPNext recent leads fetch failed: %s", exc)
        return {}, []


# ── Local DB helpers ─────────────────────────────────────────────────────

async def _fetch_usage_stats(
    user_id: str,
    db: AsyncSession,
) -> AgentUsageStats:
    """Aggregate agent usage metrics from local DB."""

    # Total runs + status breakdown
    runs_result = await db.execute(
        select(
            func.count(WorkflowRun.id),
            func.count(WorkflowRun.id).filter(WorkflowRun.status == "completed"),
            func.count(WorkflowRun.id).filter(WorkflowRun.status == "failed"),
        ).where(WorkflowRun.user_id == user_id)
    )
    row = runs_result.one()
    total_runs, completed, failed = row[0], row[1], row[2]

    # Total messages
    msg_result = await db.execute(
        select(func.count(ChatMessageLog.id))
        .join(WorkflowRun, ChatMessageLog.run_id == WorkflowRun.id)
        .where(WorkflowRun.user_id == user_id)
    )
    total_messages = msg_result.scalar() or 0

    # Total tool calls
    tool_result = await db.execute(
        select(func.count(ToolCallLog.id))
        .join(WorkflowRun, ToolCallLog.run_id == WorkflowRun.id)
        .where(WorkflowRun.user_id == user_id)
    )
    total_tool_calls = tool_result.scalar() or 0

    # Total tokens + cost from audit traces
    token_result = await db.execute(
        select(
            func.coalesce(func.sum(AuditTrace.input_tokens), 0),
            func.coalesce(func.sum(AuditTrace.output_tokens), 0),
            func.coalesce(func.sum(AuditTrace.cost_usd), 0.0),
        )
        .join(WorkflowRun, AuditTrace.run_id == WorkflowRun.id)
        .where(WorkflowRun.user_id == user_id)
    )
    tok_row = token_result.one()
    total_input = tok_row[0] or 0
    total_output = tok_row[1] or 0
    total_cost = float(tok_row[2] or 0.0)

    return AgentUsageStats(
        total_runs=total_runs,
        completed_runs=completed,
        failed_runs=failed,
        total_messages=total_messages,
        total_tool_calls=total_tool_calls,
        total_tokens_used=total_input + total_output,
        total_cost_usd=round(total_cost, 6),
    )


async def _fetch_recent_activity(
    user_id: str,
    db: AsyncSession,
    limit: int = 3,
) -> list[RecentActivity]:
    """Fetch the most recent activity items for the user."""
    items: list[RecentActivity] = []

    # Recent messages
    msg_result = await db.execute(
        select(ChatMessageLog)
        .join(WorkflowRun, ChatMessageLog.run_id == WorkflowRun.id)
        .where(WorkflowRun.user_id == user_id)
        .order_by(ChatMessageLog.created_at.desc())
        .limit(limit)
    )
    for msg in msg_result.scalars().all():
        preview = msg.content[:80] + "…" if len(msg.content) > 80 else msg.content
        items.append(RecentActivity(
            type="message",
            description=f"{'You' if msg.role == 'user' else 'Agent'}: {preview}",
            timestamp=msg.created_at.isoformat() if msg.created_at else "",
        ))

    # Recent tool calls
    tool_result = await db.execute(
        select(ToolCallLog)
        .join(WorkflowRun, ToolCallLog.run_id == WorkflowRun.id)
        .where(WorkflowRun.user_id == user_id)
        .order_by(ToolCallLog.created_at.desc())
        .limit(limit)
    )
    for tool in tool_result.scalars().all():
        status = "✗" if tool.error else "✓"
        items.append(RecentActivity(
            type="tool_call",
            description=f"{status} {tool.tool_name}",
            timestamp=tool.created_at.isoformat() if tool.created_at else "",
        ))

    # Sort combined and take the latest N
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:limit]


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full dashboard data: ERP pipeline + local usage + recent activity."""
    try:
        pipeline = await _fetch_erpnext_pipeline()
        usage = await _fetch_usage_stats(current_user.id, db)
        activity = await _fetch_recent_activity(current_user.id, db)
        categorized_leads, raw_leads = await _fetch_recent_leads()

        return DashboardResponse(
            pipeline=pipeline,
            usage=usage,
            recent_activity=activity,
            categorized_leads=categorized_leads,
            raw_leads=raw_leads,
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
        
        response = await analyze_crm_data(input_data)
        if response.get("status") == "error":
            raise HTTPException(status_code=500, detail=response.get("message"))
            
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
