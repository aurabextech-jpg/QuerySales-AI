"""Application settings — infrastructure only.

There are deliberately **no** provider credentials here. LLM, embedding, email,
ERPNext, Google Places and Google Calendar are configured per user from the
dashboard, stored AES-256-GCM encrypted, and resolved at run time by
``core/user_config.py`` (plan §54 Option A, rule §3.4).

If you are looking for where to put an API key: you are not — the user enters
it in Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database (Neon Postgres + pgvector) ──────────────────────────────
    # Must use the asyncpg driver; db/session.py normalises the Neon console
    # URL (scheme, sslmode, channel_binding) on the way in.
    DATABASE_URL: str = ""

    # ── Neon Auth (Better Auth) ──────────────────────────────────────────
    # Sign-in happens against Neon Auth; the backend only verifies the JWT
    # against the JWKS endpoint. There is no local password table.
    NEON_AUTH_URL: str = ""
    NEON_AUTH_JWKS_URL: str = ""

    # ── Security ─────────────────────────────────────────────────────────
    # One url-safe base64 32-byte key serving both AES-256-GCM (per-user
    # credentials) and the legacy Fernet column (Decision D7). Never stored in
    # Postgres, never logged. Losing it makes every stored credential
    # permanently unrecoverable.
    ENCRYPTION_KEY: str = ""

    # ── Deployment ───────────────────────────────────────────────────────
    # Injected into the public landing/legal pages (api/endpoints/pages.py).
    GOOGLE_SITE_VERIFICATION: str = ""

    # OAuth client ID handed to the frozen React Native app by
    # api/endpoints/calendar.py. Not a secret and unused by the web dashboard.
    GOOGLE_CALENDAR_IOS_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
