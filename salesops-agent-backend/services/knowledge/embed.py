"""Embedding generation via OpenAI-compatible API (plan §8, §10).

Uses the user's resolved embedding config. Asserts every returned vector
has length 1536 (Decision D2).
"""

from __future__ import annotations

import logging

from core.user_config import ResolvedEmbeddingConfig

logger = logging.getLogger(__name__)

EXPECTED_DIMENSION = 1536
BATCH_SIZE = 64


async def embed_texts(
    texts: list[str],
    cfg: ResolvedEmbeddingConfig,
) -> list[list[float]]:
    """Embed a list of texts using the user's configured provider.

    Returns one embedding vector per input text, in the same order.
    Raises on dimension mismatch (never silently pads or truncates).
    """
    if not texts:
        return []

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        logger.info(
            "Embedding batch %d-%d of %d texts (model=%s)",
            i, min(i + BATCH_SIZE, len(texts)), len(texts), cfg.model,
        )

        kwargs: dict = {
            "model": cfg.model,
            "input": batch,
        }
        # Pass dimensions parameter for providers that support it (Gemini, etc.)
        if cfg.dimension:
            kwargs["dimensions"] = cfg.dimension

        resp = await client.embeddings.create(**kwargs)

        batch_embeddings = [item.embedding for item in resp.data]

        # Assert dimension for every vector (plan §8)
        for idx, vec in enumerate(batch_embeddings):
            if len(vec) != EXPECTED_DIMENSION:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {EXPECTED_DIMENSION}, "
                    f"got {len(vec)} (batch item {i + idx}). "
                    "Check your embedding model configuration."
                )

        all_embeddings.extend(batch_embeddings)

    return all_embeddings
