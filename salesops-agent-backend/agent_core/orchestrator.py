"""SalesOps Agent Orchestrator.

Implements the autonomous agent loop using the official openai-agents SDK.

Model routing:
  Heavy  (gemini-2.5-pro)           → SalesOpsOrchestrator
  Medium (gemini-2.5-flash)         → LeadGenAgent, OutreachAgent
  Light  (OpenRouter glm-4.5-air)   → CRMAgent

Tracing is handled by DatabaseTracingProcessor (agent_core/tracing.py)
which persists ToolCallLog and AuditTrace rows automatically.
"""

import logging

from agents import (
    Agent,
    Runner,
    function_tool,
    RunContextWrapper,
    ItemHelpers,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    ModelSettings,
)
from agents.tracing import set_trace_processors

from agent_core.model_factory import build_model
from core.user_config import ResolvedLLMConfig
from agent_core.tracing import DatabaseTracingProcessor, current_run_id, flush_pending_writes

logger = logging.getLogger(__name__)

# ── Tracing ──────────────────────────────────────────────────────────────

set_trace_processors([DatabaseTracingProcessor()])

# ── Models ───────────────────────────────────────────────────────────────
# There are no module-level model singletons and no global API key: every run
# builds its agents from the authenticated user's own LLM configuration
# (rule §3.4, plan §54 Option A). See build_orchestrator() below.


# ── Agent Context ────────────────────────────────────────────────────────

from dataclasses import dataclass


@dataclass
class AgentContext:
    """Per-run context threaded to every tool via RunContextWrapper.

    The integration fields carry the authenticated user's own credentials
    (core.user_config.ResolvedIntegration). There is no shared fallback
    (rule §3.4) — a None field makes its tool report "not configured".
    """

    run_id: str
    google_refresh_token: str | None = None
    erpnext: object | None = None
    google_places: object | None = None
    google_calendar: object | None = None
    lead_sources: object | None = None
    google_dork_search: object | None = None


# ── Tool wrappers ────────────────────────────────────────────────────────

from mcp_tools.erpnext import (
    create_erpnext_lead, read_erpnext_lead, update_erpnext_lead,
    analyze_crm_data,
    CreateLeadInput, ReadLeadInput, UpdateLeadInput, AnalyzeCrmInput,
)
from mcp_tools.gmail import send_email
from mcp_tools.google_places import (
    search_businesses, search_leads_multi, get_place_details,
    SearchBusinessesInput, SearchLeadsMultiInput, GetPlaceDetailsInput,
)
from mcp_tools.google_calendar import (
    check_availability, create_event,
    CheckAvailabilityInput, CreateEventInput,
)
from mcp_tools.lead_sources import search_source_sites, SearchSourceSitesInput
from mcp_tools.google_dork import dork_search, DorkSearchInput
from mcp_tools.lead_finder import find_leads, FindLeadsInput
from mcp_tools.web_research import (
    web_search, scrape_page, research_companies,
    CompanyRef, WebSearchInput, ScrapePageInput, ResearchCompaniesInput,
)


async def _call(tool_name: str, arguments: dict, context: AgentContext = None) -> dict:
    """Route a tool-call request to the correct MCP tool implementation."""
    try:
        logger.info("Executing tool: %s", tool_name)
        # Inject context-aware tokens if needed
        if tool_name in ["check_availability", "create_event"] and context:
            arguments["refresh_token"] = context.google_refresh_token

        # Per-user credentials for the provider this tool belongs to.
        erp = context.erpnext if context else None
        places = context.google_places if context else None
        calendar = context.google_calendar if context else None
        sources = context.lead_sources if context else None
        dork = context.google_dork_search if context else None

        match tool_name:
            case "create_erpnext_lead":
                return await create_erpnext_lead(CreateLeadInput(**arguments), erp)
            case "read_erpnext_lead":
                return await read_erpnext_lead(ReadLeadInput(**arguments), erp)
            case "update_erpnext_lead":
                return await update_erpnext_lead(UpdateLeadInput(**arguments), erp)
            case "analyze_crm_data":
                return await analyze_crm_data(AnalyzeCrmInput(**arguments), erp)
            case "search_source_sites":
                return await search_source_sites(SearchSourceSitesInput(**arguments), sources)
            case "dork_search":
                return await dork_search(DorkSearchInput(**arguments), dork)
            # Web research needs no integration: it uses the user's Google key
            # when they have one and keyless DuckDuckGo otherwise.
            case "web_search":
                return await web_search(WebSearchInput(**arguments), dork)
            case "scrape_page":
                return await scrape_page(ScrapePageInput(**arguments))
            case "find_leads":
                return await find_leads(FindLeadsInput(**arguments), dork)
            case "research_companies":
                return await research_companies(ResearchCompaniesInput(**arguments), dork)
            case "send_email":
                return await send_email(
                    arguments["to_email"], arguments["subject"],
                    arguments["body"],
                )
            case "search_businesses":
                return await search_businesses(SearchBusinessesInput(**arguments), places)
            case "search_leads_multi":
                return await search_leads_multi(SearchLeadsMultiInput(**arguments), places)
            case "get_place_details":
                return await get_place_details(GetPlaceDetailsInput(**arguments), places)
            case "check_availability":
                return await check_availability(CheckAvailabilityInput(**arguments), calendar)
            case "create_event":
                return await create_event(CreateEventInput(**arguments), calendar)
            case _:
                return {"error": f"Unknown tool: {tool_name}"}
    except Exception as exc:
        logger.error("Tool failed [%s]: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc)}


# ── Function Tools (SDK-registered) ──────────────────────────────────────

@function_tool
async def create_erpnext_lead_tool(
    wrapper: RunContextWrapper[AgentContext],
    first_name: str, mobile_no: str, email_id: str,
) -> dict:
    """Create a lead in the user's ERPNext CRM. This writes a REAL record.

    The lead is created submitted (ERPNext docstatus 1), so treat it as final —
    confirm the details with the user before calling this.

    Args:
        first_name: Contact or company name for the ERPNext Lead.
        mobile_no: Phone number. Pass "" when unknown.
        email_id: Email address. Pass "" when unknown.

    Returns:
        {"status": "success", "data": {...}} with the created record, or
        {"status": "error", "reason": "not_configured"} when the user has no
        ERPNext credentials — in that case tell them to add ERPNext in
        Settings -> Integrations. Never claim the lead was created.
    """
    return await _call("create_erpnext_lead", {
        "first_name": first_name, "mobile_no": mobile_no,
        "email_id": email_id,
    }, context=wrapper.context)


@function_tool
async def read_erpnext_lead_tool(
    wrapper: RunContextWrapper[AgentContext], lead_id: str,
) -> dict:
    """Read one ERPNext Lead by its ERPNext record name.

    Args:
        lead_id: The ERPNext Lead name, e.g. "CRM-LEAD-2026-00042" — not this
                 app's own lead id and not the company name. Use
                 analyze_crm_data_tool first when you only know the name.
    """
    return await _call("read_erpnext_lead", {"lead_id": lead_id}, context=wrapper.context)


@function_tool
async def update_erpnext_lead_tool(
    wrapper: RunContextWrapper[AgentContext],
    lead_id: str, status: str = None, lead_name: str = None,
    notes: str = None, phone: str = None, email_id: str = None,
) -> dict:
    """Update an existing ERPNext Lead. Only the fields you pass are changed.

    Args:
        lead_id: The ERPNext Lead name, e.g. "CRM-LEAD-2026-00042".
        status: ERPNext lead status — one of Lead, Open, Replied, Opportunity,
                Quotation, Lost Quotation, Interested, Converted, Do Not Contact.
        lead_name: Display name of the lead.
        notes: Free-text note to store on the record.
        phone: Phone number.
        email_id: Email address.
    """
    return await _call("update_erpnext_lead", {
        "lead_id": lead_id, "status": status, "lead_name": lead_name,
        "notes": notes, "phone": phone, "email_id": email_id,
    }, context=wrapper.context)


@function_tool
async def analyze_crm_data_tool(
    wrapper: RunContextWrapper[AgentContext],
    doctype: str = "Lead", status: str = None, limit: int = 20,
) -> dict:
    """List ERPNext records so you can analyse the pipeline yourself.

    This returns RAW records, not aggregates: count and group them yourself,
    and say how many records you actually looked at. If the count equals
    `limit` there are probably more — raise the limit or filter by status
    rather than presenting a truncated slice as the whole pipeline.

    Args:
        doctype: ERPNext doctype to list — "Lead" (default), "Opportunity",
                 "Customer", "Contact".
        status: Optional exact status filter, e.g. "Open". Call once per status
                when you need a per-status breakdown.
        limit: Max records to return, newest first (default 20).
    """
    arguments: dict = {"doctype": doctype, "limit": limit}
    if status:
        arguments["filters"] = {"status": status}
    return await _call("analyze_crm_data", arguments, context=wrapper.context)


@function_tool
async def send_email_tool(
    wrapper: RunContextWrapper[AgentContext],
    to_email: str, subject: str, body: str,
) -> dict:
    """Send a real email via Gmail SMTP to a lead or attendee.

    This tool sends an actual email — it is NOT a simulation.
    The email is sent from the configured Gmail account.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body content.
    """
    return await _call("send_email", {
        "to_email": to_email, "subject": subject,
        "body": body,
    }, context=wrapper.context)


@function_tool
async def search_businesses_tool(
    wrapper: RunContextWrapper[AgentContext],
    query: str, max_results: int = 20,
) -> dict:
    """Search for businesses using Google Places."""
    return await _call("search_businesses", {
        "query": query, "max_results": max_results,
    }, context=wrapper.context)


@function_tool
async def search_leads_multi_tool(
    wrapper: RunContextWrapper[AgentContext],
    industry: str, location: str,
    max_results_per_query: int = 10,
) -> dict:
    """Primary lead discovery tool with parallel search + dedup."""
    return await _call("search_leads_multi", {
        "industry": industry, "location": location,
        "max_results_per_query": max_results_per_query,
    }, context=wrapper.context)


@function_tool
async def get_place_details_tool(
    wrapper: RunContextWrapper[AgentContext], place_id: str,
) -> dict:
    """Fetch detailed information about a place by Google Place ID."""
    return await _call("get_place_details", {
        "place_id": place_id,
    }, context=wrapper.context)


@function_tool
async def search_source_sites_tool(
    wrapper: RunContextWrapper[AgentContext],
    query: str, max_results_per_site: int = 5,
) -> dict:
    """Search the source pages this user curated in Settings for leads.

    These are the user's own trusted directories, member lists and exhibitor
    lists — usually higher-signal than a general web search, and the right
    first stop when they say "my sources", "our list", or name a directory.

    Args:
        query: What to look for, e.g. "textile exporters" or "procurement head".
               Use 3+ character words; the tool matches them against page text.
        max_results_per_site: Matching passages per page (default 5).

    Returns:
        {"status": "success", "results": [{source_url, matches, links, emails,
        phones, listings, filters, pagination}], "unreachable": [...]}.
        `listings` are the directory's company entries — pass their urls as
        `profile_url` to research_companies_tool. Cite the source_url for every lead you
        report. When "reason" is "not_configured", tell the user to add page
        URLs in Settings -> Integrations -> Lead Source Sites.
    """
    return await _call("search_source_sites", {
        "query": query, "max_results_per_site": max_results_per_site,
    }, context=wrapper.context)


@function_tool
async def dork_search_tool(
    wrapper: RunContextWrapper[AgentContext],
    query: str, max_results: int = 10,
) -> dict:
    """Search Google's public index with advanced operators to find leads.

    Use it to find companies and decision-makers that a map search cannot see:
    role titles, technologies, tender notices, membership pages.

    Args:
        query: A Google query. Combine operators for precision —
               `site:` / `-site:` to target or exclude a domain,
               `intitle:` / `inurl:` to match page titles and paths,
               `filetype:` for documents, `OR` for alternatives, and
               "quoted phrases" for exact matches.
               Example: site:linkedin.com/in "head of procurement" "Lahore"
               Example: intitle:"our members" textile association Pakistan
               Start broad, then narrow — one operator at a time.
        max_results: Results to return, max 10 per call (Google's limit).

    Returns:
        {"status": "success", "results": [{title, url, domain, snippet}]}.
        These are search-result previews, NOT verified contact details: never
        invent an email or phone number from a snippet, and cite the url for
        every lead. When "reason" is "not_configured", tell the user to add a
        Custom Search key in Settings -> Integrations.
    """
    return await _call("dork_search", {
        "query": query, "max_results": max_results,
    }, context=wrapper.context)


@function_tool
async def find_leads_tool(
    wrapper: RunContextWrapper[AgentContext],
    industry: str, city: str, source_url: str | None = None, max_leads: int = 8,
) -> dict:
    """Find, research and score companies in ONE call. Use this FIRST for discovery.

    Discovers companies (from `source_url` if the user gave one — applying that
    directory's own industry/city filters — then from web search), reads each
    company's website and contact page, and returns scored profiles: website,
    emails, phones, address, rating, social, score, tier, score_breakdown.

    Args:
        industry: What the companies do, e.g. "manufacturing", "plastic packaging".
        city: e.g. "Karachi".
        source_url: A directory or list URL the user gave, verbatim. Optional.
        max_leads: 1-8 (default 8).

    Returns:
        {"status", "leads": [...in city...], "outside_city": [...], "notes": [...]}.
        Read `notes` — they say what each source yielded (e.g. "directory lists
        0 companies for Karachi"). reason "search_blocked" means the free search
        is rate-limited: relay the message, which tells the user how to fix it.
    """
    return await _call("find_leads", {
        "industry": industry, "city": city,
        "source_url": source_url, "max_leads": max_leads,
    }, context=wrapper.context)


@function_tool
async def web_search_tool(
    wrapper: RunContextWrapper[AgentContext],
    query: str, max_results: int = 8,
) -> dict:
    """Search the public web. Always available — no integration needed.

    Use it to find candidate companies ("plastic manufacturers Karachi",
    "list of textile mills in Faisalabad") or pages about one company.

    Args:
        query: Plain search query. Include the city for local discovery.
        max_results: 1-10 results (default 8).

    Returns:
        {"status": "success", "engine", "results": [{title, url, domain, snippet}]}.
        Snippets are previews only — confirm contacts with research_companies_tool.
    """
    return await _call("web_search", {
        "query": query, "max_results": max_results,
    }, context=wrapper.context)


@function_tool
async def scrape_page_tool(
    wrapper: RunContextWrapper[AgentContext],
    url: str, include_text: bool = False,
) -> dict:
    """Read ONE web page and return only its useful structured data.

    Works on any public URL — including a directory link the user pastes in
    chat (no Settings step needed). Returns compact fields, not page text:
    title, name, description, emails, phones, address, rating, social links,
    contact_page, and for directories: `listings` (each company's detail page),
    `external_sites`, `pagination` (more result pages) and `filters` (the
    page's own search options, e.g. {"industry": [...], "location": [...]}).

    For a directory: if `filters` exist, re-scrape the URL with the filters as
    query parameters (e.g. ?industry=Manufacturing&location=Karachi) — that is
    the site's own filtering and far more accurate than reading every listing.

    Args:
        url: Absolute http(s) URL.
        include_text: Add a ~1500-character text excerpt. Only when the
            structured fields are not enough — it costs tokens.
    """
    return await _call("scrape_page", {
        "url": url, "include_text": include_text,
    }, context=wrapper.context)


@function_tool
async def research_companies_tool(
    wrapper: RunContextWrapper[AgentContext],
    companies: list[CompanyRef], city: str = "",
) -> dict:
    """Enrich up to 8 companies in ONE call: website, contacts, rating, score.

    For each company it finds the official website (web search), reads the
    homepage and, if needed, the contact page, and returns a compact profile:
    website, emails, phones, address, rating, review_count, social, sources,
    city_match, plus a 0-100 `score`, `tier` (High/Medium/Low) and
    `score_breakdown`. Read-only — call it without asking the user first.

    Args:
        companies: [{"name": "...", "website": "optional", "profile_url":
            "optional directory page about the company"}]. Pass what you
            already know — a known website or profile_url skips a search.
        city: City the user asked about; sets `city_match` for each company.
    """
    return await _call("research_companies", {
        "companies": [c.model_dump() for c in companies], "city": city,
    }, context=wrapper.context)


@function_tool
async def check_availability_tool(
    wrapper: RunContextWrapper[AgentContext],
    date: str, timezone: str = "Asia/Karachi",
) -> dict:
    """Check the user's real Google Calendar availability for a specific date.

    This tool calls the Google Calendar FreeBusy API to return actual busy time slots.
    You MUST call this tool before creating any calendar event.

    Args:
        date: The date to check in YYYY-MM-DD format (e.g., '2026-05-20').
              MUST be an absolute date, not relative ('tomorrow').
        timezone: IANA timezone string (default: 'Asia/Karachi').

    Returns:
        A dict with 'busy_slots' (list of {start, end} time ranges when the user is busy)
        and 'date'. If busy_slots is empty, the entire day is free.
    """
    return await _call("check_availability", {
        "date": date, "timezone": timezone,
    }, context=wrapper.context)


@function_tool
async def create_event_tool(
    wrapper: RunContextWrapper[AgentContext],
    summary: str, start_datetime: str, end_datetime: str = None,
    description: str = "", timezone: str = "Asia/Karachi",
    attendee_emails: list[str] = None,
) -> dict:
    """Create a real event on the user's Google Calendar.

    This tool calls the Google Calendar Events API to insert a new event.
    You MUST call check_availability_tool first to verify the time slot is free.

    Args:
        summary: Event title (e.g., 'Demo call with Al-Shifa Clinic').
        start_datetime: ISO-8601 start time WITHOUT timezone suffix.
                        Format: 'YYYY-MM-DDTHH:MM:SS' (e.g., '2026-05-20T10:00:00').
                        DO NOT append 'Z' or '+05:00'.
        end_datetime: ISO-8601 end time, same format. If omitted, defaults to 1 hour after start.
        description: Optional event body text / meeting notes.
        timezone: IANA timezone (default: 'Asia/Karachi'). The API uses this for both start and end.
        attendee_emails: List of email addresses to invite (e.g., ['client@example.com']).

    Returns:
        A dict with event_id, summary, start, end, and html_link (Google Calendar link).
    """
    return await _call("create_event", {
        "summary": summary, "start_datetime": start_datetime,
        "end_datetime": end_datetime, "description": description,
        "timezone": timezone, "attendee_emails": attendee_emails or [],
    }, context=wrapper.context)


# ── Agent factory ────────────────────────────────────────────────────────

SALES_AGENT_SYSTEM_PROMPT = """\
Role: SalesOps Orchestrator — autonomous lead-gen specialist + ERPNext CRM operator.

You manage specialized agents:
- lead_generation: Discover and enrich leads from three sources — Google Places (local businesses),
  the user's own curated source pages, and targeted Google operator ("dork") search of the public web.
- crm_management: Manage and analyze records in the user's ERPNext CRM. ERPNext is an OPTIONAL
  outbound integration, not this app's lead store, and it only works if that user configured it.
- outreach: Draft emails, check REAL Google Calendar availability, and create REAL calendar events.

# Strategy
1. Delegate lead discovery to `lead_generation` IMMEDIATELY. Pass the industry, the city, any URL
   the user gave (verbatim), and what they want back (e.g. "with contact details"). NEVER ask the
   user to pick a source: `lead_generation` uses every available source plus built-in web search,
   and researches each company's website, phone, email and rating itself.
   Delegate ONCE per user message and present what comes back — do not call `lead_generation`
   again in the same turn to "try harder"; each call re-runs the whole search.
   For follow-ups about earlier leads ("get their contact info", "research these"), delegate again
   with the company names AND any URLs that appeared earlier in the conversation.
2. Delegate CRM tasks (creating/reading/updating leads, pipeline analysis) to `crm_management`.
3. Delegate ALL scheduling, meeting, availability, and email tasks to `outreach`. This agent has access to the user's real Google Calendar — it is NOT a simulation.
4. When leads are discovered, proactively ask the user which ones they want to add to the CRM, then delegate to `crm_management`.
5. After adding leads to the CRM, suggest next steps like scheduling a follow-up call or sending an introductory email.

# Lead Workflow
- `lead_generation` returns leads already researched and scored (tier + 0-100 score). Keep its
  scores, contact columns and source links — do not re-score, drop columns, or summarise them away.
- Group leads by score: **High Opportunity** first, then **Medium**, then **Low**.
- Always ask: "Would you like me to add any of these leads to your CRM? You can filter by score or pick specific ones."
- When adding leads to CRM, pass: name, email, phone, and the source URL reported for that lead.

# Autonomy & Ambiguity Protocol
- Read-only work needs NO permission: searching, reading web pages, looking up contact details,
  scoring. Just do it and report the result.
- Ask before WRITES only: creating/updating CRM records, sending email, creating calendar events.
- Ask ONE clarification question only when a required parameter is truly missing (e.g. no
  industry AND no city for discovery, or no lead-ID for an update). Do NOT guess parameters.

# Time & Date Resolution
- You will receive the 'Current Date and Time' in the [System Context] of your input.
- Always resolve relative dates (e.g., "tomorrow", "next week") to absolute dates (e.g., "2026-05-18") BEFORE delegating to any sub-agents.
- If no date/time is provided for an action that requires one, assume the current or next upcoming suitable time based on the context.

# Multilingual Support
- You can understand and respond in multiple languages including English, Urdu, Arabic, and Roman Urdu.
- Always respond in the SAME language the user used in their message.
- If the user writes in Urdu/Roman Urdu, reply in Urdu/Roman Urdu while keeping technical terms (lead names, IDs, tool names) in English.

# Output Formatting Rules (CRITICAL)
- Currency: PKR. Dates: DD-MMM-YYYY. Phone: +92-xxx.
- The interface renders full markdown — tables, **bold**, *italics*, lists, `code` and links all
  display correctly. Choose the format that fits the data:
  - **Markdown table** for 4+ items sharing the same fields (lead lists, pipeline breakdowns).
  - **Bold-titled bullets** for 1-3 items, or when each item carries different detail.
- Example table:
  | Company | Tier (score) | Phone | Email | Website | Rating | City | Source |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | Al-Shifa Clinic | High (82) | +92-42-35761234 | info@alshifa.pk | alshifa.pk | 4.5 (230) | Lahore | Google Places |
- Example bullets:
  **Al-Shifa Clinic** (Opportunity: High)
  - Address: 45-A, Main Boulevard, Gulberg III, Lahore
  - Rating: 4.5 ⭐ (230 reviews)
  - Phone: +92-42-35761234
- Always end with a "**Next Best Action**" suggestion.
- Keep responses focused, professional, and actionable.

# Scope & Boundaries
- You are STRICTLY a SalesOps assistant. You handle: lead generation, CRM management, email outreach, and calendar scheduling.
- If the user asks about topics outside your scope (e.g., coding, general knowledge, jokes, weather, news), politely decline:
  "I appreciate your message, but I'm specialized in sales operations — lead generation, CRM management, and outreach. How can I help you with those?"
- Do NOT engage with casual chat, jokes, or off-topic discussions.

# ANTI-HALLUCINATION RULES (MANDATORY)
- You do NOT have direct access to tools. You MUST delegate to the appropriate sub-agent.
- For ANY calendar/scheduling request (check availability, create meeting, schedule call), you MUST delegate to `outreach`.
- NEVER fabricate calendar availability, event links, event IDs, or email confirmations.
- NEVER say "I've created a meeting" or "Your calendar shows..." unless you actually delegated to `outreach` and received a real tool response.
- If the user's Google Calendar is not connected, inform them: "Please connect your Google Calendar from the Account screen first."
- Always pass the user's exact date/time intent to `outreach`. Resolve relative dates (e.g., 'tomorrow') to absolute dates BEFORE delegating.
"""


# Turn budgets. A turn is one model call; lead research is discover -> verify
# -> enrich -> report plus the odd retry, which overran the SDK default of 10
# and surfaced to users as "The agent could not complete your request".
ORCHESTRATOR_MAX_TURNS = 12
LEAD_GEN_MAX_TURNS = 16


def build_orchestrator(llm_cfg: ResolvedLLMConfig) -> Agent[AgentContext]:
    """Build the orchestrator and its sub-agents for one user, one run.

    All four agents share the caller's single configured model. The old
    heavy/medium/light tiering is gone with the global keys: a user
    configures one provider, so there is only one model to route to.
    """
    model = build_model(llm_cfg)
    model_settings = ModelSettings(include_usage=True)

    lead_gen_agent = Agent[AgentContext](
    name="LeadGenAgent",
    model=model,
    model_settings=model_settings,
    instructions=(
        "You are a specialized Lead Generation Agent. Your job is to discover and enrich potential business leads.\n\n"
        "## Work autonomously\n"
        "Finding and researching companies is read-only, so never stop to ask which source to use\n"
        "or whether to look up contact details — do the whole job in one pass:\n"
        "DISCOVER -> VERIFY -> ENRICH -> SCORE -> REPORT.\n"
        "\n"
        "## 0. FAST PATH — use this first\n"
        "For any 'find <industry> companies in <city>' request (with or without a URL), call\n"
        "`find_leads_tool` ONCE. It discovers, researches and scores in a single call. If it\n"
        "returns leads, go straight to REPORT. Use the steps below only to add to its results\n"
        "(e.g. Google Places when configured) or when the user asks about specific companies.\n"
        "\n"
        "## 1. DISCOVER — collect candidate companies\n"
        "- The user gave a URL: call `scrape_page_tool` on it. A directory returns `listings`,\n"
        "  `filters` and `pagination`. If `filters` cover the request (industry, city), re-scrape with\n"
        "  them as query parameters, e.g. ?industry=Manufacturing&location=Karachi — the site's own\n"
        "  filter beats guessing. If the filtered page lists 0 companies, say so plainly: that source\n"
        "  has none, which is an answer, not a failure. Then fall back to web search.\n"
        "- No URL: run every source that is available: `search_leads_multi_tool` (Google Places —\n"
        "  ratings and phones), `search_source_sites_tool` (the user's curated pages) and\n"
        "  `web_search_tool` (always available). For web search, ask for lists, e.g.\n"
        "  'plastic manufacturers in Karachi', 'top textile companies Karachi list'.\n"
        "  Use `scrape_page_tool` on a promising list/directory result to pull its `listings`.\n"
        "- `dork_search_tool` is for decision-makers and niche signals (site:linkedin.com/in ...).\n"
        "- A source returning reason 'not_configured' is simply skipped — keep going with the others,\n"
        "  and mention it in one line at the end ('Skipped: Google Places (not configured)').\n"
        "\n"
        "## 2. VERIFY — keep only real matches\n"
        "- A candidate must be a named company, not a menu label, category or article title.\n"
        "- Drop or flag companies whose evidence contradicts the requested city or industry.\n"
        "\n"
        "## 3. ENRICH — one call, up to 8 companies\n"
        "Call `research_companies_tool` ONCE with the best candidates (max 8) and the city. Pass any\n"
        "website or directory `profile_url` you already have — it skips a search and is more accurate.\n"
        "Places results already carry phone/rating; enrich them only if website or email is missing.\n"
        "Never ask the user for a company's URL or contact details — finding them is your job.\n"
        "\n"
        "## 4. SCORE\n"
        "Start from each company's `score` / `tier` (contact completeness + reputation, explained in\n"
        "`score_breakdown`). Adjust by up to ±15 for fit with the user's request and say why.\n"
        "`city_match: false` means the company is based elsewhere — lower it to Low or list it\n"
        "separately as 'outside <city>'. Places-only leads: High = rating ≥ 4.0 with ≥ 100 reviews\n"
        "and phone + website; Medium = rating ≥ 3.5 or ≥ 50 reviews with one contact; else Low.\n"
        "\n"
        "## 5. REPORT\n"
        "Table columns: Company | Tier (score) | Phone | Email | Website | Rating | City | Source.\n"
        "Group High, then Medium, then Low. Put a short 'Why' line under the table for the top leads.\n"
        "Use '—' for anything not found; never leave the user to look it up.\n"
        "\n"
        "## Source integrity (MANDATORY)\n"
        "- Report ONLY what a tool returned. Never invent an email, phone, rating or company.\n"
        "- Search snippets are previews; contacts come from `research_companies_tool` or\n"
        "  `scrape_page_tool`. Cite a source URL for every lead.\n"
        "- Never answer from your own knowledge of companies.\n"
        "\n"
        "## Efficiency\n"
        "- Prefer the batch tool over many single calls; never scrape the same URL twice.\n"
        "- Leave `include_text` off unless the structured fields are genuinely insufficient.\n"
        "- End by offering to add the High/Medium leads to the CRM — that is a write, so it needs a yes.\n"
    ),
    tools=[
        search_leads_multi_tool, search_businesses_tool, get_place_details_tool,
        search_source_sites_tool, dork_search_tool,
        find_leads_tool, web_search_tool, scrape_page_tool, research_companies_tool,
    ],
    )

    crm_agent = Agent[AgentContext](
    name="CRMAgent",
    model=model,
    model_settings=model_settings,
    instructions=(
        "You are a specialized CRM Management Agent operating the user's own ERPNext instance.\n"
        "Every tool below performs a REAL call against it. There is no simulation or dry-run mode:\n"
        "if you call a write tool, the record changes.\n\n"
        "## Your tools\n"
        "1. `create_erpnext_lead_tool(first_name, mobile_no, email_id)` — creates a Lead.\n"
        "   All three arguments are required; pass \"\" for any the user did not give you.\n"
        "   The record is created SUBMITTED, so it is final — read the details back to the user\n"
        "   and get their go-ahead before calling it, and never batch-create without asking.\n"
        "2. `read_erpnext_lead_tool(lead_id)` — one lead by its ERPNext name, e.g.\n"
        "   \"CRM-LEAD-2026-00042\". A company name is NOT a lead_id: when you only have a name,\n"
        "   find the record with `analyze_crm_data_tool` first and use the `name` field it returns.\n"
        "3. `update_erpnext_lead_tool(lead_id, status=, lead_name=, notes=, phone=, email_id=)` —\n"
        "   only the arguments you pass are written. Valid ERPNext statuses: Lead, Open, Replied,\n"
        "   Opportunity, Quotation, Lost Quotation, Interested, Converted, Do Not Contact.\n"
        "4. `analyze_crm_data_tool(doctype=, status=, limit=)` — lists RAW records; it does not\n"
        "   aggregate. Count and group them yourself. For a per-status breakdown, call it once per\n"
        "   status. Always tell the user how many records you actually examined, and if the count\n"
        "   came back equal to `limit` say the view may be truncated instead of implying it is the\n"
        "   whole pipeline. `doctype` accepts Lead (default), Opportunity, Customer, Contact.\n\n"
        "## ERPNext is optional and outbound only\n"
        "- This app's own leads live in its database, not in ERPNext. ERPNext is where the user\n"
        "  pushes records OUT to. Do not describe it as the source of truth for their pipeline.\n"
        "- If a tool returns reason 'not_configured', ERPNext credentials are missing for this user.\n"
        "  Say exactly that and point them to Settings -> Integrations. NEVER claim a lead was\n"
        "  created, updated or found, and never invent a lead ID, when the tool did not succeed.\n"
        "- If a tool returns an error, report the actual failure rather than retrying blindly.\n\n"
        "## Output Rules\n"
        "- Markdown renders properly here: use a table when listing 4+ records with the same fields,\n"
        "  bold labels and bullets for anything shorter.\n"
        "- When listing leads, show: name (the ERPNext ID), lead_name, status, source, created.\n"
        "- After creating or updating a lead, confirm with the ERPNext lead ID the tool returned.\n"
        "- Proactively suggest next actions (e.g., 'Would you like to schedule a follow-up?').\n"
    ),
    tools=[
        create_erpnext_lead_tool, read_erpnext_lead_tool,
        update_erpnext_lead_tool, analyze_crm_data_tool,
    ],
    )

    outreach_agent = Agent[AgentContext](
    name="OutreachAgent",
    model=model,
    model_settings=model_settings,
    instructions=(
        "You are a specialized Outreach Agent focused on communications and scheduling.\n"
        "You have access to REAL tools that interact with LIVE services. You MUST call them — NEVER fabricate or hallucinate results.\n\n"
        "## CRITICAL RULES\n"
        "1. You MUST call the actual tools provided to you. NEVER make up calendar data, email confirmations, or event links.\n"
        "2. If a tool returns an error, report the EXACT error to the user. Do NOT pretend the action succeeded.\n"
        "3. If a tool is unavailable or credentials are missing, tell the user to connect their Google Calendar first.\n\n"
        "## Email Strategy\n"
        "1. Draft and send emails using `send_email_tool`.\n"
        "2. Write professional, concise emails with a clear subject line and call-to-action.\n\n"
        "## Calendar & Scheduling Strategy (MANDATORY WORKFLOW)\n"
        "When the user asks to schedule a meeting, check availability, or create an event, follow this EXACT workflow:\n\n"
        "### Step 1: Check Availability\n"
        "ALWAYS call `check_availability_tool` FIRST with the target date.\n"
        "- Parameter `date`: MUST be in 'YYYY-MM-DD' format (e.g., '2026-05-20'). Convert relative dates like 'tomorrow' or 'next Monday' to absolute dates.\n"
        "- Parameter `timezone`: Default 'Asia/Karachi'.\n"
        "- The tool returns real busy_slots from the user's Google Calendar. Report these to the user.\n\n"
        "### Step 2: Create Event (only after Step 1)\n"
        "Call `create_event_tool` with these parameters:\n"
        "- `summary`: A descriptive title (e.g., 'Sales Demo — Al-Shifa Clinic').\n"
        "- `start_datetime`: ISO-8601 format WITHOUT timezone suffix: 'YYYY-MM-DDTHH:MM:SS' (e.g., '2026-05-20T10:00:00').\n"
        "- `end_datetime`: Same format. If not specified, omit it (defaults to 1 hour after start).\n"
        "- `description`: Meeting notes or agenda.\n"
        "- `timezone`: 'Asia/Karachi' (default).\n"
        "- `attendee_emails`: List of email strings to invite.\n\n"
        "### Step 3: Confirm to User\n"
        "After the tool returns, report the ACTUAL result:\n"
        "- Event title, start/end time, attendees, and the Google Calendar link (html_link).\n"
        "- If the tool returned an error, show the error — do NOT make up a fake confirmation.\n\n"
        "## Output Rules\n"
        "- Markdown renders properly here: use bold headings, bullets, and a table when listing\n"
        "  several time slots or recipients with the same fields.\n"
        "- Always confirm actions with REAL data from tool responses.\n"
        "- NEVER invent event IDs, calendar links, or time slots.\n"
    ),
    tools=[send_email_tool, check_availability_tool, create_event_tool],
    )

    return Agent[AgentContext](
        name="SalesOpsOrchestrator",
        model=model,
        model_settings=model_settings,
        instructions=SALES_AGENT_SYSTEM_PROMPT,
        tools=[
            lead_gen_agent.as_tool(
                tool_name="lead_generation",
                tool_description=(
                    "Discover companies, research their websites and contact details, and score "
                    "them. Fully autonomous and read-only — pass industry, city, any URLs and "
                    "company names; it chooses sources itself."
                ),
                max_turns=LEAD_GEN_MAX_TURNS,
            ),
            crm_agent.as_tool(
                tool_name="crm_management",
                tool_description="Manage and analyze CRM data",
            ),
            outreach_agent.as_tool(
                tool_name="outreach",
                tool_description=(
                    "Draft and send emails, check REAL Google Calendar availability, "
                    "and create REAL calendar events. Delegate here for ANY scheduling, "
                    "meeting, availability, or email task. This agent calls live APIs — "
                    "it does NOT simulate or fabricate results."
                ),
            ),
        ],
    )


# ── Helper: build full prompt from message history ───────────────────────

from datetime import datetime

def _get_current_datetime_context() -> str:
    """Returns the current date and time formatted for the agent."""
    now = datetime.now()
    # E.g., 'Monday, 2026-05-17 03:45 PM'
    formatted = now.strftime("%A, %Y-%m-%d %I:%M %p")
    return (
        f"\n[System Context]\n"
        f"Current Date and Time: {formatted}\n"
        f"Use this current date/time to resolve any relative time references in the user's request "
        f"(e.g., 'tomorrow', 'next Monday', 'in 2 days').\n"
    )

def _build_input(messages: list[dict]) -> str:
    """Serialize conversation history into a single prompt string."""
    last_user_msg = ""
    for msg in reversed(messages):
        role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role == "user":
            last_user_msg = content
            break

    history = "\n".join(
        f"{m['role'] if isinstance(m, dict) else m.role}: "
        f"{m['content'] if isinstance(m, dict) else m.content}"
        for m in messages
    )
    
    time_context = _get_current_datetime_context()
    return f"Conversation History:\n{history}\n{time_context}\nUser Request: {last_user_msg}"


# ── Public API: non-streaming ────────────────────────────────────────────

async def _update_run_status(run_id: str, status: str) -> None:
    """Update the WorkflowRun row status (completed / failed)."""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import update
            from db.models import WorkflowRun
            await session.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id)
                .values(status=status)
            )
            await session.commit()
            logger.info("WorkflowRun %s → %s", run_id, status)
    except Exception:
        logger.exception("Failed to update run status for %s", run_id)


async def run_orchestrator(
    messages: list,
    *,
    llm_config: ResolvedLLMConfig,
    run_id: str | None = None,
    google_refresh_token: str | None = None,
    integrations: dict | None = None,
) -> str:
    """Run the agent orchestration loop (non-streaming)."""
    token = current_run_id.set(run_id)
    creds = integrations or {}
    try:
        context = AgentContext(
            run_id=run_id or "",
            google_refresh_token=google_refresh_token,
            erpnext=creds.get("erpnext"),
            google_places=creds.get("google_places"),
            google_calendar=creds.get("google_calendar"),
            lead_sources=creds.get("lead_sources"),
            google_dork_search=creds.get("google_dork_search"),
        )
        result = await Runner.run(
            starting_agent=build_orchestrator(llm_config),
            input=_build_input(messages),
            context=context,
            max_turns=ORCHESTRATOR_MAX_TURNS,
        )
        output = result.final_output or "I processed your request but didn't generate a text response."
        # Flush all queued tracing writes before the response returns
        await flush_pending_writes()
        if run_id:
            await _update_run_status(run_id, "completed")
        return output
    except Exception:
        if run_id:
            await _update_run_status(run_id, "failed")
        await flush_pending_writes()
        raise
    finally:
        current_run_id.reset(token)


# ── Public API: structured response with events ─────────────────────────

from openai.types.responses import ResponseTextDeltaEvent
from db.session import AsyncSessionLocal


async def run_orchestrator_with_events(
    messages: list,
    *,
    llm_config: ResolvedLLMConfig,
    run_id: str | None = None,
    google_refresh_token: str | None = None,
    integrations: dict | None = None,
) -> dict:
    """Run the agent loop and collect all events into a structured response.

    Returns:
        {
            "steps": [
                {"type": "agent",       "agent": "AgentName"},
                {"type": "tool_start",  "tool":  "tool_name"},
                {"type": "tool_result", "tool":  "tool_name", "content": "..."},
            ],
            "message": "Final agent response text",
        }

    This replaces the SSE generator because Vercel's Python runtime
    buffers entire responses — true streaming is not possible.
    """
    token = current_run_id.set(run_id)
    steps: list[dict] = []
    current_tool_name = "unknown"
    creds = integrations or {}

    try:
        context = AgentContext(
            run_id=run_id or "",
            google_refresh_token=google_refresh_token,
            erpnext=creds.get("erpnext"),
            google_places=creds.get("google_places"),
            google_calendar=creds.get("google_calendar"),
            lead_sources=creds.get("lead_sources"),
            google_dork_search=creds.get("google_dork_search"),
        )
        result = Runner.run_streamed(
            starting_agent=build_orchestrator(llm_config),
            input=_build_input(messages),
            context=context,
            max_turns=ORCHESTRATOR_MAX_TURNS,
        )

        logger.info("Agent run started for run_id=%s", run_id)

        async for event in result.stream_events():
            # ── Agent hand-off (thinking indicator) ──────────────────
            if event.type == "agent_updated_stream_event":
                agent_name = event.new_agent.name
                logger.info("Agent hand-off → %s (run=%s)", agent_name, run_id)
                steps.append({"type": "agent", "agent": agent_name})

            # ── Tool lifecycle ───────────────────────────────────────
            elif event.type == "run_item_stream_event":
                item = event.item

                if item.type == "tool_call_item":
                    current_tool_name = getattr(
                        item, "name",
                        getattr(
                            getattr(item, "raw_item", None), "name", "unknown"
                        ),
                    )
                    logger.info("Tool call: %s (run=%s)", current_tool_name, run_id)
                    steps.append({"type": "tool_start", "tool": current_tool_name})

                elif item.type == "tool_call_output_item":
                    output_preview = str(item.output)[:500]
                    steps.append({
                        "type": "tool_result",
                        "tool": current_tool_name,
                        "content": output_preview,
                    })

            # Token deltas are not collected — we use final_output

        # Run complete — flush tracing writes
        await flush_pending_writes()

        final = result.final_output or "I processed your request but didn't generate a text response."
        logger.info("Agent run completed for run_id=%s (output_len=%d)", run_id, len(final))

        if run_id:
            await _update_run_status(run_id, "completed")

        return {"steps": steps, "message": final}

    except Exception as exc:
        logger.error("Agent run error (run=%s): %s", run_id, exc, exc_info=True)
        await flush_pending_writes()
        if run_id:
            await _update_run_status(run_id, "failed")
        raise
    finally:
        current_run_id.reset(token)


