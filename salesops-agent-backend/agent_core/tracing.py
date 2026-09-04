"""Custom TracingProcessor — persists tool calls and audit traces to Postgres.

The SDK's TracingProcessor callbacks are **synchronous**, so we collect
coroutines in a pending-writes queue and flush them at the end of the
orchestrator run.  This is critical on Vercel serverless where
`asyncio.create_task` fire-and-forget coroutines are silently cancelled
when the response finishes.

Architecture (from SDK docs):
  - `span.span_data` holds the typed data object (FunctionSpanData, etc.)
  - `span.span_data.type` returns the string discriminator

Span types captured:
  function   → ToolCallLog  (individual tool invocation)
  agent      → AuditTrace   (sub-agent delegation record)
  generation → AuditTrace   (LLM reasoning step + tokens/cost)
  handoff    → AuditTrace   (agent hand-off record)
"""

import asyncio
import json
import logging
from contextvars import ContextVar
from datetime import datetime

from agents.tracing import TracingProcessor

from db.models import ToolCallLog, AuditTrace
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ── Context variable — set by the orchestrator before each Runner call ───
current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)

# ── Pending writes queue ────────────────────────────────────────────────
_pending_writes: list = []


async def flush_pending_writes() -> None:
    """Await all queued DB writes before the serverless function exits."""
    global _pending_writes
    writes = _pending_writes.copy()
    _pending_writes.clear()
    if not writes:
        return
    logger.info("Flushing %d pending DB writes…", len(writes))
    results = await asyncio.gather(*writes, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Pending write %d failed: %s", i, result, exc_info=result)
    logger.info("Flush complete — %d writes processed.", len(results))


# ── Approximate pricing per 1M tokens (USD) ─────────────────────────────
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash":      {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "z-ai/glm-4.5-air:free": {"input": 0.0,  "output": 0.0},
}


def _estimate_cost(model: str | None, input_t: int, output_t: int) -> float | None:
    """Estimate USD cost for a generation span."""
    if not model or (input_t == 0 and output_t == 0):
        return None
    prices = MODEL_PRICING.get(model)
    if not prices:
        return None
    cost = (
        (input_t / 1_000_000) * prices["input"]
        + (output_t / 1_000_000) * prices["output"]
    )
    return round(cost, 8) if cost > 0 else None


# ── Token extraction helper ─────────────────────────────────────────────

def _extract_tokens(usage) -> tuple[int, int]:
    """Extract input/output token counts from various usage formats.

    The SDK may pass usage as:
      - None
      - A dict: {"input_tokens": N, "output_tokens": M}
      - A Usage/CompletionUsage object with attributes
      - Keys may be input_tokens/output_tokens OR prompt_tokens/completion_tokens
    """
    if usage is None:
        return 0, 0

    if isinstance(usage, dict):
        in_tok = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or 0
        )
        out_tok = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or 0
        )
        return int(in_tok), int(out_tok)

    # Object with attributes (Usage dataclass, CompletionUsage, etc.)
    in_tok = (
        getattr(usage, "input_tokens", None)
        or getattr(usage, "prompt_tokens", None)
        or 0
    )
    out_tok = (
        getattr(usage, "output_tokens", None)
        or getattr(usage, "completion_tokens", None)
        or 0
    )
    return int(in_tok), int(out_tok)


# ── Queue helper ─────────────────────────────────────────────────────────

def _enqueue(coro) -> None:
    """Append an async coroutine to the pending-writes queue."""
    _pending_writes.append(coro)


# ── DB persistence helpers ───────────────────────────────────────────────

def _now() -> datetime:
    return datetime.utcnow()


async def _write_tool_call(
    run_id: str,
    tool_name: str,
    input_data: dict | None,
    output_data: dict | str | None,
    error: str | None,
    duration_ms: int | None = None,
) -> None:
    """Insert a ToolCallLog row."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(ToolCallLog(
                run_id=run_id,
                tool_name=tool_name,
                input_data=input_data or {},
                output_data=(
                    output_data if isinstance(output_data, dict)
                    else {"raw": str(output_data)} if output_data else {}
                ),
                error=error,
                duration_ms=duration_ms,
                created_at=_now(),
            ))
            await session.commit()
        logger.info("✓ ToolCallLog: tool=%s run=%s", tool_name, run_id)
    except Exception:
        logger.exception("✗ ToolCallLog failed: tool=%s", tool_name)


async def _write_audit_trace(
    run_id: str,
    agent_name: str,
    thought: str,
    *,
    model_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Insert an AuditTrace row."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(AuditTrace(
                run_id=run_id,
                agent_name=agent_name,
                thought_process=thought,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                created_at=_now(),
            ))
            await session.commit()
        logger.info(
            "✓ AuditTrace: agent=%s model=%s tokens=%s/%s run=%s",
            agent_name, model_name, input_tokens, output_tokens, run_id,
        )
    except Exception:
        logger.exception("✗ AuditTrace failed: agent=%s", agent_name)


# ── JSON helpers ─────────────────────────────────────────────────────────

def _safe_json(val: str | dict | None) -> dict | None:
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {"raw": str(val)}


# ── Agent ↔ Model mapping ───────────────────────────────────────────────
# Maps model identifiers back to the agent that uses them, so generation
# spans can be attributed to the correct agent instead of the model name.

AGENT_MODEL_MAP: dict[str, str] = {}  # populated at module init


def register_agent_model(agent_name: str, model_id: str) -> None:
    """Register which agent uses which model. Called from orchestrator."""
    AGENT_MODEL_MAP[model_id] = agent_name
    logger.debug("Registered model mapping: %s → %s", model_id, agent_name)


def _resolve_agent_for_model(model: str | None) -> str:
    """Look up the agent name for a model, falling back to 'LLM'."""
    if not model:
        return "LLM"
    return AGENT_MODEL_MAP.get(model, model)


# ── DatabaseTracingProcessor ────────────────────────────────────────────

class DatabaseTracingProcessor(TracingProcessor):
    """Intercepts SDK trace/span lifecycle and queues DB writes.

    Tracks the currently active agent via a stack so that LLM
    generation spans are correctly attributed to the calling agent
    rather than storing the model name as the agent_name.
    """

    def __init__(self) -> None:
        self._agent_stack: list[str] = []

    @property
    def _current_agent(self) -> str:
        return self._agent_stack[-1] if self._agent_stack else "SalesOpsOrchestrator"

    # ── Trace lifecycle ──────────────────────────────────────────────

    def on_trace_start(self, trace) -> None:
        run_id = current_run_id.get()
        self._agent_stack.clear()
        logger.info(
            "[Trace START] trace_id=%s workflow=%s run_id=%s",
            getattr(trace, "trace_id", "?"),
            getattr(trace, "name", "?"),
            run_id,
        )

    def on_trace_end(self, trace) -> None:
        run_id = current_run_id.get()
        if not run_id:
            return
        workflow = getattr(trace, "name", "SalesOpsOrchestrator")
        _enqueue(_write_audit_trace(
            run_id=run_id,
            agent_name=workflow,
            thought=f"Workflow '{workflow}' completed.",
        ))

    # ── Span lifecycle ───────────────────────────────────────────────

    def on_span_start(self, span) -> None:
        sd = getattr(span, "span_data", None)
        if not sd:
            return
        span_type = getattr(sd, "type", None)

        # Track the active agent so generation spans know who called them
        if span_type == "agent":
            agent_name = getattr(sd, "name", "UnknownAgent")
            self._agent_stack.append(agent_name)
            logger.debug("[Span START] agent=%s", agent_name)
        else:
            logger.debug("[Span START] type=%s", span_type)

    def on_span_end(self, span) -> None:
        run_id = current_run_id.get()
        if not run_id:
            return

        sd = getattr(span, "span_data", None)
        if sd is None:
            return

        span_type = getattr(sd, "type", "unknown")
        span_error = getattr(span, "_error", None) or getattr(span, "error", None)

        # ── function → ToolCallLog ───────────────────────────────
        if span_type == "function":
            tool_name = getattr(sd, "name", "unknown_tool")
            started = getattr(span, "_started_at", None)
            ended = getattr(span, "_ended_at", None)
            dur = None
            if started and ended:
                try:
                    dur = int((ended - started) * 1000)
                except Exception:
                    pass

            logger.info("[Span END] function=%s run=%s", tool_name, run_id)
            _enqueue(_write_tool_call(
                run_id=run_id,
                tool_name=tool_name,
                input_data=_safe_json(getattr(sd, "input", None)),
                output_data=_safe_json(
                    str(getattr(sd, "output", None))
                    if getattr(sd, "output", None) is not None
                    else None
                ),
                error=str(span_error) if span_error else None,
                duration_ms=dur,
            ))

        # ── agent → AuditTrace ───────────────────────────────────
        elif span_type == "agent":
            name = getattr(sd, "name", "UnknownAgent")
            tools = getattr(sd, "tools", []) or []
            tool_names = [str(t) for t in tools]

            # Pop the agent stack (this agent is done)
            if self._agent_stack and self._agent_stack[-1] == name:
                self._agent_stack.pop()

            logger.info("[Span END] agent=%s run=%s", name, run_id)
            _enqueue(_write_audit_trace(
                run_id=run_id,
                agent_name=name,
                thought=(
                    f"Agent '{name}' completed execution."
                    + (f" Tools available: {tool_names}" if tool_names else "")
                ),
            ))

        # ── generation → AuditTrace with tokens + cost ───────────
        elif span_type == "generation":
            model = getattr(sd, "model", None)
            raw_usage = getattr(sd, "usage", None)
            in_tok, out_tok = _extract_tokens(raw_usage)
            cost = _estimate_cost(model, in_tok, out_tok)

            # Use the currently active agent name, NOT the model name
            agent_name = self._current_agent

            # Build a descriptive thought
            thought_parts = [f"LLM generation by '{agent_name}'"]
            if model:
                thought_parts.append(f"using {model}")
            if in_tok or out_tok:
                thought_parts.append(f"— {in_tok:,} input / {out_tok:,} output tokens")
            if cost is not None:
                thought_parts.append(f"(est. ${cost:.6f})")

            # Log raw usage for debugging token extraction
            logger.info(
                "[Span END] generation model=%s agent=%s "
                "raw_usage=%s extracted=%d/%d run=%s",
                model, agent_name, raw_usage, in_tok, out_tok, run_id,
            )

            _enqueue(_write_audit_trace(
                run_id=run_id,
                agent_name=agent_name,
                thought=" ".join(thought_parts),
                model_name=model,
                input_tokens=in_tok if in_tok > 0 else None,
                output_tokens=out_tok if out_tok > 0 else None,
                cost_usd=cost,
            ))

        # ── handoff → AuditTrace ─────────────────────────────────
        elif span_type == "handoff":
            from_a = getattr(sd, "from_agent", "?")
            to_a = getattr(sd, "to_agent", "?")
            logger.info("[Span END] handoff %s → %s run=%s", from_a, to_a, run_id)
            _enqueue(_write_audit_trace(
                run_id=run_id,
                agent_name=from_a,
                thought=f"Delegated from '{from_a}' to '{to_a}'",
            ))

    # ── Required interface methods ───────────────────────────────────

    def shutdown(self) -> None:
        logger.info("DatabaseTracingProcessor shutting down.")

    def force_flush(self) -> None:
        pass
