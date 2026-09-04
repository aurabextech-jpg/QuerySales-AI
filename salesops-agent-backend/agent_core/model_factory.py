"""Per-user model factory (rule §3.4, plan §52).

Breaks the global-singleton pattern in orchestrator.py. Called per-run with
the authenticated user's resolved config, not module-level env vars.
"""

from __future__ import annotations

from agents import AsyncOpenAI, OpenAIChatCompletionsModel

from core.user_config import ResolvedLLMConfig


def build_model(cfg: ResolvedLLMConfig) -> OpenAIChatCompletionsModel:
    """Build an OpenAI-compatible model from a resolved per-user config.

    Same shape as ``orchestrator.py:_make_model`` but instantiated per run.
    """
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    return OpenAIChatCompletionsModel(
        model=cfg.model,
        openai_client=client,
    )
