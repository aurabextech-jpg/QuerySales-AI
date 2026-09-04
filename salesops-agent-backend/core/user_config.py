"""Per-user configuration resolution (plan §52, §54).

Resolution order for each config type:
    1. The authenticated user's DB row (decrypted server-side).
    2. Optional system-fallback env vars (``LLM_*``, ``EMBEDDING_*``).
    3. Raise :class:`ConfigurationMissing` → 400 with an actionable message.

The returned dataclasses carry *decrypted* values.  They never cross a
response boundary — they exist only for the duration of one request.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from core.crypto import decrypt_secret
from core.integrations import IntegrationSpec, env_defaults, get_spec
from db.models import (
    User,
    UserEmailConfig,
    UserEmbeddingConfig,
    UserIntegrationConfig,
    UserLLMConfig,
)

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


# ── Third-party integrations (plan §41) ────────────────────────────────────


@dataclass(frozen=True)
class ResolvedIntegration:
    """Decrypted credentials for one third-party provider.

    ``values`` merges the stored public config with the decrypted secrets, so
    callers read every field the same way. Never serialised into a response.
    """

    provider: str
    values: dict[str, str]
    source: str  # "user" | "env"

    def get(self, name: str, default: str = "") -> str:
        return self.values.get(name) or default

    @property
    def complete(self) -> bool:
        """True when every required field for this provider has a value."""
        spec = get_spec(self.provider)
        return all(self.values.get(f) for f in spec.required_fields)


def _decrypt_secrets(row: UserIntegrationConfig, spec: IntegrationSpec) -> dict[str, str]:
    """Decrypt the provider's secret blob into a plain dict.

    A blob that cannot be decrypted — key rotated, row corrupted — is treated
    as "no secrets" rather than raising, so one bad row cannot take down every
    settings page and agent run for that user.
    """
    if not row.secrets_encrypted:
        return {}
    try:
        return {
            k: v
            for k, v in json.loads(decrypt_secret(row.secrets_encrypted)).items()
            if k in spec.secret_fields and v
        }
    except Exception:
        logger.warning(
            "Could not decrypt %s secrets for user %s — treating as unconfigured",
            row.provider,
            row.user_id,
        )
        return {}


async def resolve_integration_config(
    user_id: str,
    provider: str,
    db: AsyncSession,
) -> ResolvedIntegration | None:
    """Resolve one integration for *user_id*.

    Order: the user's row → optional env fallback → ``None``.

    Returns ``None`` rather than raising: every integration here is optional
    and must never block a response when unconfigured (Decision D5).
    """
    spec = get_spec(provider)

    result = await db.execute(
        select(UserIntegrationConfig).where(
            UserIntegrationConfig.user_id == user_id,
            UserIntegrationConfig.provider == provider,
        )
    )
    row = result.scalars().first()

    if row and row.enabled:
        values = {
            k: v
            for k, v in (row.config or {}).items()
            if k in spec.public_fields and v
        }
        values.update(_decrypt_secrets(row, spec))
        if any(values.values()):
            return ResolvedIntegration(provider=provider, values=values, source="user")

    fallback = env_defaults(spec)
    if fallback:
        return ResolvedIntegration(provider=provider, values=fallback, source="env")

    return None


async def resolve_calendar_credentials(
    user: User,
    db: AsyncSession,
) -> ResolvedIntegration | None:
    """Google Calendar credentials, preferring the account's connected token.

    The Connect Calendar OAuth flow stores a refresh token on ``users`` with
    the legacy Fernet cipher (Decision D3 leaves that column alone). That token
    wins over anything pasted into Settings, because it is the one the user
    actually authorised.
    """
    resolved = await resolve_integration_config(user.id, "google_calendar", db)

    if user.google_refresh_token:
        try:
            from core.security import decrypt_token

            token = decrypt_token(user.google_refresh_token)
        except Exception:
            logger.warning("Could not decrypt stored calendar token for user %s", user.id)
            token = ""
        if token:
            values = dict(resolved.values) if resolved else {}
            values["refresh_token"] = token
            return ResolvedIntegration(
                provider="google_calendar",
                values=values,
                source=resolved.source if resolved else "user",
            )

    return resolved
