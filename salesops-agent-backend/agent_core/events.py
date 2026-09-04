"""Semantic phase events (plan §6, §20).

Emits AgentEvent rows with a monotonic sequence per run, driving the live
analysis timeline UI (polled via GET /api/runs/{id}/events, Decision D6).

Reuses tracing.py's pending-write + flush discipline for serverless safety.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from db.models import AgentEvent

logger = logging.getLogger(__name__)

# Phase constants
OBSERVE = "OBSERVE"
RETRIEVE = "RETRIEVE"
REASON = "REASON"
PLAN = "PLAN"
TOOL_CALL = "TOOL_CALL"
RESULT = "RESULT"
COMPLETE = "COMPLETE"
ERROR = "ERROR"


async def emit(
    db: AsyncSession,
    *,
    run_id: str,
    user_id: str,
    phase: str,
    title: str,
    detail: str | None = None,
    payload: dict | None = None,
) -> AgentEvent:
    """Emit a semantic event with a monotonic sequence number.

    The sequence is scoped per run — it increments from the last event's
    sequence for that run_id.
    """
    # Get the next sequence number
    result = await db.execute(
        select(func.coalesce(func.max(AgentEvent.sequence), -1)).where(
            AgentEvent.run_id == run_id
        )
    )
    next_seq = result.scalar() + 1

    event = AgentEvent(
        run_id=run_id,
        user_id=user_id,
        phase=phase,
        title=title,
        detail=detail,
        payload=payload,
        sequence=next_seq,
    )
    db.add(event)
    await db.commit()

    logger.info(
        "Event [%s] run=%s seq=%d phase=%s: %s",
        event.id[:8], run_id[:8], next_seq, phase, title,
    )
    return event
