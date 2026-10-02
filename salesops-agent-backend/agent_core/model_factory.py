"""Per-user model factory (rule §3.4, plan §52).

Breaks the global-singleton pattern in orchestrator.py. Called per-run with
the authenticated user's resolved config, not module-level env vars.
"""

from __future__ import annotations

import re

from agents import AsyncOpenAI, ModelSettings, OpenAIChatCompletionsModel
from agents.retry import ModelRetrySettings, RetryDecision, RetryPolicyContext
from openai.types.shared import Reasoning

from core.user_config import ResolvedLLMConfig

LLM_TIMEOUT_SECONDS = 90.0
# Retries honour the provider's retry-after on 429 — free tiers (Groq: 8k TPM)
# throttle for a few seconds at a time, which a retry absorbs invisibly.
LLM_MAX_RETRIES = 3

# Runner-level retries for failures the HTTP client does not retry (a 400).
MODEL_CALL_RETRIES = 2
MALFORMED_TOOL_CALL_DELAY = 0.5
RATE_LIMIT_FALLBACK_DELAY = 5.0
# A longer wait is a daily quota, not a burst — fail fast and say so.
MAX_RATE_LIMIT_WAIT = 30.0

# Small open models (gpt-oss-20b on Groq) sometimes emit tool arguments that are
# not valid JSON or do not match the schema; Groq rejects the whole completion
# with a 400 "tool_use_failed". Re-sampling the same request almost always works.
_MALFORMED_TOOL_CALL_MARKERS = (
    "tool_use_failed",
    "tool call validation failed",
    "failed to parse tool call",
)
# Models that accept `reasoning_effort`. Others reject the parameter, so it is
# only sent where it is known to work.
_REASONING_MODEL_RE = re.compile(r"(^|/)(gpt-oss|o[134]|gpt-5)", re.I)


def build_model(cfg: ResolvedLLMConfig) -> OpenAIChatCompletionsModel:
    """Build an OpenAI-compatible model from a resolved per-user config.

    Same shape as ``orchestrator.py:_make_model`` but instantiated per run.
    """
    # The SDK default is a 600 s timeout with 2 retries, so one stalled provider
    # call could freeze a chat for half an hour. 90 s fits a long tool-heavy
    # completion; a stall now fails fast and chat.py reports it.
    client = AsyncOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )
    return OpenAIChatCompletionsModel(
        model=cfg.model,
        openai_client=client,
    )


def _retry_flaky_model_calls(ctx: RetryPolicyContext) -> bool | RetryDecision:
    message = str(ctx.error).lower()
    if any(marker in message for marker in _MALFORMED_TOOL_CALL_MARKERS):
        return RetryDecision(retry=True, delay=MALFORMED_TOOL_CALL_DELAY, reason="malformed tool call")
    if ctx.normalized.status_code == 429:
        wait = ctx.normalized.retry_after or RATE_LIMIT_FALLBACK_DELAY
        if wait <= MAX_RATE_LIMIT_WAIT:
            return RetryDecision(retry=True, delay=wait, reason="rate limited")
    return False


def build_model_settings(cfg: ResolvedLLMConfig) -> ModelSettings:
    """Settings shared by every agent in a run.

    Low reasoning effort: on gpt-oss the default effort spent ~1,000 hidden
    reasoning tokens per call — more than the visible answer — against an
    8k-tokens-per-minute budget.
    """
    reasoning = Reasoning(effort="low") if _REASONING_MODEL_RE.search(cfg.model or "") else None
    return ModelSettings(
        include_usage=True,
        reasoning=reasoning,
        retry=ModelRetrySettings(max_retries=MODEL_CALL_RETRIES, policy=_retry_flaky_model_calls),
    )
