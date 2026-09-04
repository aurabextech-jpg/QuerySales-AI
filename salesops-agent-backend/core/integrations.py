"""Integration provider registry (plan §41 ``user_integration_config``).

Declares, for every third-party integration, which fields it takes, which of
those are secret, and which env var each falls back to. One table
(:class:`db.models.UserIntegrationConfig`) and one set of endpoints then serve
every provider — adding another is a change to this file alone, no migration.

Secrets declared here are AES-256-GCM encrypted at rest and never leave the
server (plan §45-47). Non-secret fields — base URLs, client IDs — are stored
in plain JSON so the settings UI can show them back to the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.config import settings


@dataclass(frozen=True)
class IntegrationField:
    """One configurable field of an integration."""

    name: str
    label: str
    secret: bool = False
    required: bool = True
    placeholder: str = ""
    help: str = ""


@dataclass(frozen=True)
class IntegrationSpec:
    """Everything the generic settings endpoints need to serve a provider."""

    provider: str
    label: str
    description: str
    fields: tuple[IntegrationField, ...]
    # field name → Settings attribute used as the optional system fallback
    env_fallback: dict[str, str] = field(default_factory=dict)

    @property
    def secret_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.secret)

    @property
    def public_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if not f.secret)

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)


# ── Registry ───────────────────────────────────────────────────────────────

INTEGRATIONS: dict[str, IntegrationSpec] = {
    "erpnext": IntegrationSpec(
        provider="erpnext",
        label="ERPNext CRM",
        description=(
            "Optional outbound CRM. Leads live in this app's database "
            "(Decision D5); ERPNext is only used to push records out."
        ),
        fields=(
            IntegrationField(
                name="base_url",
                label="Base URL",
                placeholder="https://erp.example.com",
            ),
            IntegrationField(
                name="api_token",
                label="API token",
                secret=True,
                placeholder="api_key:api_secret",
                help="ERPNext token in the form api_key:api_secret.",
            ),
        ),
        env_fallback={
            "base_url": "ERPNEXT_BASE_URL",
            "api_token": "ERPNEXT_API_TOKEN",
        },
    ),
    "google_places": IntegrationSpec(
        provider="google_places",
        label="Google Places",
        description="Business discovery and enrichment for the chat agent.",
        fields=(
            IntegrationField(
                name="api_key",
                label="API key",
                secret=True,
                placeholder="AIza…",
            ),
        ),
        env_fallback={"api_key": "GOOGLE_PLACES_API_KEY"},
    ),
    "google_calendar": IntegrationSpec(
        provider="google_calendar",
        label="Google Calendar",
        description="Availability lookups and meeting creation for the chat agent.",
        fields=(
            IntegrationField(
                name="client_id",
                label="OAuth client ID",
                placeholder="…apps.googleusercontent.com",
            ),
            IntegrationField(
                name="client_secret",
                label="OAuth client secret",
                secret=True,
                placeholder="GOCSPX-…",
            ),
            IntegrationField(
                name="refresh_token",
                label="Refresh token",
                secret=True,
                required=False,
                help=(
                    "Optional here — the Connect Calendar flow stores this on "
                    "your account. Paste one only for a headless setup."
                ),
            ),
        ),
        env_fallback={
            "client_id": "GOOGLE_CALENDAR_CLIENT_ID",
            "client_secret": "GOOGLE_CALENDAR_CLIENT_SECRET",
            "refresh_token": "GOOGLE_CALENDAR_REFRESH_TOKEN",
        },
    ),
}

PROVIDERS: tuple[str, ...] = tuple(INTEGRATIONS)


def get_spec(provider: str) -> IntegrationSpec:
    """Look up a provider spec. Raises KeyError for an unknown provider."""
    return INTEGRATIONS[provider]


def env_defaults(spec: IntegrationSpec) -> dict[str, str]:
    """Values this provider would fall back to from the environment.

    Empty strings are dropped so a half-configured fallback never masquerades
    as a complete one.
    """
    out: dict[str, str] = {}
    for field_name, attr in spec.env_fallback.items():
        value = getattr(settings, attr, "") or ""
        if value:
            out[field_name] = value
    return out
