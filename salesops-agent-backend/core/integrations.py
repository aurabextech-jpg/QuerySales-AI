"""Integration provider registry (plan §41 ``user_integration_config``).

Declares, for every third-party integration, which fields it takes, which of
those are secret. One table
(:class:`db.models.UserIntegrationConfig`) and one set of endpoints then serve
every provider — adding another is a change to this file alone, no migration.

Secrets declared here are AES-256-GCM encrypted at rest and never leave the
server (plan §45-47). Non-secret fields — base URLs, client IDs — are stored
in plain JSON so the settings UI can show them back to the user.

There is no environment fallback: every user supplies their own credentials
(plan §54 Option A).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationField:
    """One configurable field of an integration."""

    name: str
    label: str
    secret: bool = False
    required: bool = True
    placeholder: str = ""
    help: str = ""
    # Renders as a textarea instead of a single-line input. The value is still
    # one string — a list-valued field (lead source sites) is stored as one
    # URL per line, which keeps every layer's dict[str, str] typing intact.
    multiline: bool = False


@dataclass(frozen=True)
class IntegrationSpec:
    """Everything the generic settings endpoints need to serve a provider."""

    provider: str
    label: str
    description: str
    fields: tuple[IntegrationField, ...]

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
    ),
    "lead_sources": IntegrationSpec(
        provider="lead_sources",
        label="Lead Source Sites",
        description=(
            "Your own list of public pages the agent may search for leads — "
            "directories, member lists, exhibitor lists, industry news."
        ),
        fields=(
            IntegrationField(
                name="site_urls",
                label="Source page URLs",
                multiline=True,
                placeholder=(
                    "https://chamber.example.org/members\n"
                    "https://expo.example.com/exhibitors"
                ),
                help=(
                    "One URL per line, up to 10. The agent fetches each page and "
                    "returns the passages, links and contacts matching its query."
                ),
            ),
        ),
    ),
    "google_dork_search": IntegrationSpec(
        provider="google_dork_search",
        label="Google Dork Search",
        description=(
            "Targeted web search over Google's public index using advanced "
            "operators (site:, intitle:, inurl:) for lead discovery."
        ),
        fields=(
            IntegrationField(
                name="api_key",
                label="Custom Search API key",
                secret=True,
                placeholder="AIza…",
                help="A Google Cloud API key with the Custom Search API enabled.",
            ),
            IntegrationField(
                name="cx",
                label="Search engine ID (cx)",
                placeholder="a1b2c3d4e5f6g7h8i",
                help=(
                    "From programmablesearchengine.google.com. Set it to search "
                    "the entire web, otherwise site: operators cannot match."
                ),
            ),
        ),
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
    ),
}

PROVIDERS: tuple[str, ...] = tuple(INTEGRATIONS)


def get_spec(provider: str) -> IntegrationSpec:
    """Look up a provider spec. Raises KeyError for an unknown provider."""
    return INTEGRATIONS[provider]


