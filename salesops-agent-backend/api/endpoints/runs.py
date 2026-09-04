"""Workflow run endpoints — create, list, get runs + events for the logged-in user."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from db.models import User, WorkflowRun, ToolCallLog, AuditTrace, AgentEvent, Lead
from db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────

class WorkflowRunCreate(BaseModel):
    workflow_type: str
    mode: str = "simulation"


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    mode: str
    workflow_type: str
    created_at: datetime | None = None
    # Phase 5 additions
    lead_id: str | None = None
    final_result: dict | None = None
    completed_at: datetime | None = None


class WorkflowRunSummary(BaseModel):
    """Lightweight run summary for the list endpoint."""
    id: str
    status: str
    mode: str
    workflow_type: str
    created_at: datetime | None = None
    tool_call_count: int = 0
    trace_count: int = 0
    # Phase 5 additions
    lead_id: str | None = None
    lead_company: str | None = None
    score: int | None = None
    qualification: str | None = None
    completed_at: datetime | None = None


# ── POST /api/runs — create a new run ────────────────────────────────────

@router.post("/", response_model=WorkflowRunResponse)
async def create_run(
    run_in: WorkflowRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initialize a new workflow run."""
    try:
        db_run = WorkflowRun(
            user_id=current_user.id,
            workflow_type=run_in.workflow_type,
            mode=run_in.mode,
            status="running",
        )
        db.add(db_run)
        await db.commit()
        await db.refresh(db_run)
        return db_run
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_run failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create workflow run. Please try again.",
        )


# ── GET /api/runs — list all runs for logged-in user ─────────────────────

@router.get("/", response_model=list[WorkflowRunSummary])
async def list_runs(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List workflow runs for the authenticated user, newest first."""
    try:
        result = await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.user_id == current_user.id)
            .order_by(WorkflowRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        runs = result.scalars().all()

        summaries = []
        for run in runs:
            # Count associated tool calls
            tc_result = await db.execute(
                select(func.count())
                .select_from(ToolCallLog)
                .where(ToolCallLog.run_id == run.id)
            )
            tool_count = tc_result.scalar() or 0

            # Count associated audit traces
            at_result = await db.execute(
                select(func.count())
                .select_from(AuditTrace)
                .where(AuditTrace.run_id == run.id)
            )
            trace_count = at_result.scalar() or 0

            summaries.append(WorkflowRunSummary(
                id=run.id,
                status=run.status,
                mode=run.mode,
                workflow_type=run.workflow_type,
                created_at=run.created_at,
                tool_call_count=tool_count,
                trace_count=trace_count,
                lead_id=run.lead_id,
                lead_company=None,  # populated below
                score=(run.final_result or {}).get("lead_score"),
                qualification=(run.final_result or {}).get("qualification"),
                completed_at=run.completed_at,
            ))

        # Populate lead company for runs that have a lead_id
        lead_ids = {s.lead_id for s in summaries if s.lead_id}
        if lead_ids:
            leads_result = await db.execute(
                select(Lead).where(Lead.id.in_(lead_ids))
            )
            lead_map = {l.id: l.company for l in leads_result.scalars().all()}
            for s in summaries:
                if s.lead_id:
                    s.lead_company = lead_map.get(s.lead_id)

        return summaries
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("list_runs failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve workflow runs.",
        )


# ── GET /api/runs/{run_id} — get a specific run ─────────────────────────

@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status of a specific workflow run."""
    try:
        result = await db.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id,
                WorkflowRun.user_id == current_user.id,
            )
        )
        run = result.scalars().first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_run failed for run_id=%s: %s", run_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve workflow run.",
        )


# ── GET /api/runs/{run_id}/events — phase timeline (Decision D6) ─────────


class AgentEventResponse(BaseModel):
    id: str
    phase: str
    title: str
    detail: str | None = None
    payload: dict | None = None
    sequence: int
    created_at: datetime | None = None


@router.get("/{run_id}/events", response_model=list[AgentEventResponse])
async def get_run_events(
    run_id: str,
    after_sequence: int = Query(0, ge=0, description="Only return events after this sequence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the ordered phase events for a run. Supports incremental polling."""
    # Verify ownership
    run_result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    if not run_result.scalars().first():
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(AgentEvent)
        .where(
            AgentEvent.run_id == run_id,
            AgentEvent.user_id == current_user.id,
            AgentEvent.sequence > after_sequence,
        )
        .order_by(AgentEvent.sequence.asc())
    )
    events = result.scalars().all()
    return [
        AgentEventResponse(
            id=e.id,
            phase=e.phase,
            title=e.title,
            detail=e.detail,
            payload=e.payload,
            sequence=e.sequence,
            created_at=e.created_at,
        )
        for e in events
    ]
