"""Per-user configuration resolution (plan §52, §54).

Resolution order for each config type:
    1. The authenticated user's DB row (decrypted server-side).
    2. Optional system-fallback env vars (``LLM_*``, ``EMBEDDING_*``).
    3. Raise :class:`ConfigurationMissing` → 400 with an actionable message.

The returned dataclasses carry *decrypted* values.  They never cross a
response boundary — they exist only for the duration of one request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from core.crypto import decrypt_secret
from db.models import UserLLMConfig, UserEmbeddingConfig, UserEmailConfig

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────────


class ConfigurationMissing(Exception):
    """Raised when neither the user row nor the env fallback provides a value.

    Mapped to a 400 with an actionable message — never a 500.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# ── Resolved config dataclasses ────────────────────────────────────────────


@dataclass(frozen=True)
class ResolvedLLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass(frozen=True)
class ResolvedEmbeddingConfig:
    base_url: str
    api_key: str
    model: str
    dimension: int = 1536


@dataclass(frozen=True)
class ResolvedEmailConfig:
    provider: str
    email_address: str
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_password: str | None = None
    access_token: str | None = None


# ── Resolvers ──────────────────────────────────────────────────────────────


async def resolve_llm_config(user_id: str, db: AsyncSession) -> ResolvedLLMConfig:
    """Resolve the LLM config for *user_id*.

    Falls back to ``LLM_*`` env vars if the user has no row.
    """
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    )
    row = result.scalars().first()

    if row:
        return ResolvedLLMConfig(
            base_url=row.base_url,
            api_key=decrypt_secret(row.api_key_encrypted),
            model=row.model,
            temperature=row.temperature or 0.7,
            max_tokens=row.max_tokens or 4096,
        )

    # System fallback
    if settings.LLM_BASE_URL and settings.LLM_API_KEY:
        return ResolvedLLMConfig(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )

    raise ConfigurationMissing(
        "LLM provider not configured. Go to Settings → AI / LLM and add your "
        "provider details, or ask an administrator to set system-wide defaults."
    )


async def resolve_embedding_config(
    user_id: str, db: AsyncSession
) -> ResolvedEmbeddingConfig:
    """Resolve the embedding config for *user_id*.

    Falls back to ``EMBEDDING_*`` env vars if the user has no row.
    """
    result = await db.execute(
        select(UserEmbeddingConfig).where(UserEmbeddingConfig.user_id == user_id)
    )
    row = result.scalars().first()

    if row:
        return ResolvedEmbeddingConfig(
            base_url=row.base_url,
            api_key=decrypt_secret(row.api_key_encrypted),
            model=row.model,
            dimension=row.dimension,
        )

    # System fallback
    if settings.EMBEDDING_BASE_URL and settings.EMBEDDING_API_KEY:
        return ResolvedEmbeddingConfig(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )

    raise ConfigurationMissing(
        "Embedding provider not configured. Go to Settings → Embeddings and "
        "add your provider details."
    )


async def resolve_email_config(
    user_id: str, db: AsyncSession
) -> ResolvedEmailConfig | None:
    """Resolve the email config for *user_id*.

    Returns ``None`` if neither the user row nor the env fallback is set.
    Email is optional — the agent can still run, it just cannot send outreach.
    """
    result = await db.execute(
        select(UserEmailConfig).where(UserEmailConfig.user_id == user_id)
    )
    row = result.scalars().first()

    if row:
        return ResolvedEmailConfig(
            provider=row.provider,
            email_address=row.email_address,
            smtp_host=row.smtp_host,
            smtp_port=row.smtp_port,
            smtp_password=(
                decrypt_secret(row.smtp_password_encrypted)
                if row.smtp_password_encrypted
                else None
            ),
            access_token=(
                decrypt_secret(row.access_token_encrypted)
                if row.access_token_encrypted
                else None
            ),
        )

    # System fallback: legacy Gmail env vars
    if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
        return ResolvedEmailConfig(
            provider="gmail_smtp",
            email_address=settings.GMAIL_USER,
            smtp_host=settings.GMAIL_SMTP_HOST,
            smtp_port=settings.GMAIL_SMTP_PORT,
            smtp_password=settings.GMAIL_APP_PASSWORD,
        )

    return None
