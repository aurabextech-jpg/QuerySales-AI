"""Trace-logs endpoint — feeds the Antigravity Trace Viewer in the mobile app.

GET /api/workflows/{run_id}/logs

Returns a timeline of audit traces and tool-call logs for a given
workflow run, formatted to match the frontend TraceLogsScreen contract:

  { run_id, logs: [{ id, timestamp, agent, action, details, status }] }
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from db.models import User, WorkflowRun, AuditTrace, ToolCallLog
from db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response models ──────────────────────────────────────────────────────

class LogEntry(BaseModel):
    id: str
    timestamp: str
    agent: str
    action: str
    details: str
    status: str  # "success" | "error"


class TraceLogsResponse(BaseModel):
    run_id: str
    logs: list[LogEntry]


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.get("/{run_id}/logs", response_model=TraceLogsResponse)
async def get_trace_logs(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return merged audit traces + tool-call logs for a workflow run."""
    try:
        # Verify the run belongs to the authenticated user
        run_result = await db.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id,
                WorkflowRun.user_id == current_user.id,
            )
        )
        run = run_result.scalars().first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        logs: list[LogEntry] = []

        # ── Tool-call logs ───────────────────────────────────────────────
        tool_result = await db.execute(
            select(ToolCallLog)
            .where(ToolCallLog.run_id == run_id)
            .order_by(ToolCallLog.created_at.asc())
        )
        for tool_log in tool_result.scalars().all():
            # Build a human-readable detail string from output
            details = ""
            if tool_log.error:
                details = f"Error: {tool_log.error}"
            elif isinstance(tool_log.output_data, dict):
                details = tool_log.output_data.get(
                    "message",
                    tool_log.output_data.get("status", "completed"),
                )
            else:
                details = "Tool call completed"

            logs.append(
                LogEntry(
                    id=tool_log.id,
                    timestamp=tool_log.created_at.isoformat() if tool_log.created_at else "",
                    agent="Tool Executor",
                    action=tool_log.tool_name or "unknown",
                    details=str(details),
                    status="error" if tool_log.error else "success",
                )
            )

        # ── Audit traces ─────────────────────────────────────────────────
        trace_result = await db.execute(
            select(AuditTrace)
            .where(AuditTrace.run_id == run_id)
            .order_by(AuditTrace.created_at.asc())
        )
        for trace in trace_result.scalars().all():
            logs.append(
                LogEntry(
                    id=trace.id,
                    timestamp=trace.created_at.isoformat() if trace.created_at else "",
                    agent=trace.agent_name or "Orchestrator",
                    action="agent_decision",
                    details=trace.thought_process or "",
                    status="success",
                )
            )

        # Sort everything by timestamp
        logs.sort(key=lambda entry: entry.timestamp)

        return TraceLogsResponse(run_id=run_id, logs=logs)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_trace_logs failed for run_id=%s: %s", run_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve trace logs.",
        )
