from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SalesOps Agent"

    # ── Database (Neon Postgres) ─────────────────────────────────────────
    DATABASE_URL: str = ""

    # ── Neon Auth (Better Auth) ──────────────────────────────────────────
    NEON_AUTH_URL: str = ""
    NEON_AUTH_JWKS_URL: str = ""

    # ── ERPNext ──────────────────────────────────────────────────────────
    ERPNEXT_BASE_URL: str = ""
    ERPNEXT_API_TOKEN: str = ""

    # ── Google ───────────────────────────────────────────────────────────
    GOOGLE_PLACES_API_KEY: str = ""
    # Web client ID/secret — used for backend token exchange (Android + iOS)
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    # iOS-specific native client ID (created in Google Cloud Console → iOS app type)
    GOOGLE_CALENDAR_IOS_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_REFRESH_TOKEN: str = ""

    # ── Gmail SMTP ───────────────────────────────────────────────────────
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_SMTP_HOST: str = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int = 587

    # ── Gemini (tiered models via OpenAI-compatible endpoint) ────────────
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL_HEAVY: str = "gemini-2.5-pro"          # orchestrator
    GEMINI_MODEL_MEDIUM: str = "gemini-2.5-flash"       # lead gen, outreach
    GEMINI_MODEL_LIGHT: str = "gemini-2.5-flash-lite"   # simple lookups

    # ── OpenRouter (OpenAI-compatible, for CRM agent) ────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "z-ai/glm-4.5-air:free"

    # ── Security ─────────────────────────────────────────────────────────
    ENCRYPTION_KEY: str = ""

    # ── Verification ─────────────────────────────────────────────────────
    GOOGLE_SITE_VERIFICATION: str = "bmcSvmYPsn3dPLi50H2NSQGPgpFFHJTvn0g7OUhw7BA"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
