"""Per-user model factory (rule §3.4, plan §52).

Breaks the global-singleton pattern in orchestrator.py. Called per-run with
the authenticated user's resolved config, not module-level env vars.
"""

from __future__ import annotations

from agents import AsyncOpenAI, OpenAIChatCompletionsModel

from core.user_config import ResolvedLLMConfig

LLM_TIMEOUT_SECONDS = 90.0
# Retries honour the provider's retry-after on 429 — free tiers (Groq: 8k TPM)
# throttle for a few seconds at a time, which a retry absorbs invisibly.
LLM_MAX_RETRIES = 3


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
