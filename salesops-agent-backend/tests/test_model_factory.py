"""Model settings: reasoning gating and the retry policy for flaky model calls."""

import dataclasses

from agents.retry import ModelRetryNormalizedError, RetryDecision, RetryPolicyContext

from agent_core.model_factory import _retry_flaky_model_calls, build_model_settings
from agent_core.orchestrator import _build_input
from core.user_config import ResolvedLLMConfig


def _cfg(model: str) -> ResolvedLLMConfig:
    values = {f.name: "x" for f in dataclasses.fields(ResolvedLLMConfig)}
    return ResolvedLLMConfig(**{**values, "model": model, "base_url": "http://x"})


def _ctx(error: Exception, status: int | None = None, retry_after: float | None = None):
    return RetryPolicyContext(
        error=error, attempt=1, max_retries=2, stream=False,
        normalized=ModelRetryNormalizedError(status_code=status, retry_after=retry_after),
    )


def test_low_reasoning_only_for_models_that_accept_it():
    assert build_model_settings(_cfg("openai/gpt-oss-20b")).reasoning.effort == "low"
    assert build_model_settings(_cfg("gpt-5-mini")).reasoning.effort == "low"
    assert build_model_settings(_cfg("gemini-2.5-flash")).reasoning is None
    assert build_model_settings(_cfg("llama-3.3-70b-versatile")).reasoning is None


def test_malformed_tool_calls_are_retried():
    error = Exception("Error code: 400 - {'code': 'tool_use_failed'}")
    decision = _retry_flaky_model_calls(_ctx(error, status=400))
    assert isinstance(decision, RetryDecision) and decision.retry


def test_short_rate_limits_retry_but_daily_quota_fails_fast():
    short = _retry_flaky_model_calls(_ctx(Exception("429"), status=429, retry_after=2.0))
    assert isinstance(short, RetryDecision) and short.delay == 2.0
    assert _retry_flaky_model_calls(_ctx(Exception("429"), status=429, retry_after=885.0)) is False


def test_other_errors_are_not_retried():
    assert _retry_flaky_model_calls(_ctx(Exception("bad key"), status=401)) is False


def test_build_input_drops_system_prompt_and_clips_history():
    text = _build_input([
        {"role": "system", "content": "SECRET PROMPT"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "x" * 5000},
        {"role": "user", "content": "find plastic companies in Karachi"},
    ])
    assert "SECRET PROMPT" not in text
    assert text.endswith("User: find plastic companies in Karachi")
    assert len(text) < 1500
