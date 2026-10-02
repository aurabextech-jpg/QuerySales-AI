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
)
from agents.tracing import set_trace_processors

from agent_core.model_factory import build_model, build_model_settings
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
    # From the authenticated request — never from the model. Scopes writes to
    # the app's own tables (save_leads_tool).
    user_id: str | None = None
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
from services.lead_import import LeadToSave, save_leads
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
    """Create one lead in the user's ERPNext CRM (a real record). One call per lead.

    Args:
        first_name: Company or contact name.
        mobile_no: One phone number, or "" when unknown.
        email_id: One email address, or "" when unknown.

    Returns {"status": "success", "data": {...}} or {"status": "error", ...};
    reason "not_configured" means ERPNext is not set up.
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
    """Search the user's curated source pages (Settings -> Lead Source Sites).

    Args:
        query: Words of 3+ characters to match.
        max_results_per_site: Passages per page.

    Results include each page's listings (company pages) and filters.
    """
    return await _call("search_source_sites", {
        "query": query, "max_results_per_site": max_results_per_site,
    }, context=wrapper.context)


@function_tool
async def dork_search_tool(
    wrapper: RunContextWrapper[AgentContext],
    query: str, max_results: int = 10,
) -> dict:
    """Google search with operators (site:, intitle:, inurl:, "quotes", OR), for
    decision-makers and niche signals. Results are previews, not verified contacts.

    Args:
        query: e.g. site:linkedin.com/in "head of procurement" "Karachi".
        max_results: 1-10.
    """
    return await _call("dork_search", {
        "query": query, "max_results": max_results,
    }, context=wrapper.context)


@function_tool
async def save_leads_tool(
    wrapper: RunContextWrapper[AgentContext],
    leads: list[LeadToSave],
) -> dict:
    """Save confirmed leads to the user's Leads page; also pushes each to ERPNext when configured.

    Args:
        leads: Up to 10, each with company plus any of contact_name, email, phone,
            website, industry, city, notes. Copy values from the conversation.

    Returns per-lead saved / skipped (duplicate), with erpnext_id when pushed.
    """
    ctx = wrapper.context
    if not ctx.user_id:
        return {"status": "error", "message": "No authenticated user for this run."}
    return await save_leads(ctx.user_id, leads, ctx.erpnext)


@function_tool
async def find_leads_tool(
    wrapper: RunContextWrapper[AgentContext],
    industry: str, city: str, source_url: str | None = None, max_leads: int = 8,
) -> dict:
    """Find, research and score up to 8 companies in one call.

    Args:
        industry: e.g. "manufacturing".
        city: e.g. "Karachi".
        source_url: Directory/list URL the user gave, verbatim.
        max_leads: 1-8.

    Returns {leads, outside_city, notes}; notes explain empty results.
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
    """Search the public web. Snippets are previews, not verified contacts.

    Args:
        query: Search query; include the city for local results.
        max_results: 1-10.
    """
    return await _call("web_search", {
        "query": query, "max_results": max_results,
    }, context=wrapper.context)


@function_tool
async def scrape_page_tool(
    wrapper: RunContextWrapper[AgentContext],
    url: str, include_text: bool = False,
) -> dict:
    """Read one public URL; returns contacts, rating, social links, and for directories
    listings, filters and pagination.

    Args:
        url: Absolute http(s) URL.
        include_text: Add a 1500-char text excerpt; costs tokens, use rarely.
    """
    return await _call("scrape_page", {
        "url": url, "include_text": include_text,
    }, context=wrapper.context)


@function_tool
async def research_companies_tool(
    wrapper: RunContextWrapper[AgentContext],
    companies: list[CompanyRef], city: str = "",
) -> dict:
    """Research up to 8 companies: website, emails, phones, address, rating, score, tier.

    Args:
        companies: Each with name, plus website or profile_url when known.
        city: Requested city; sets city_match.
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
You are QuerySales, a sales-ops assistant: lead generation, CRM, email and scheduling only.
Decline anything else in one polite sentence.

Tools
- find_leads_tool: "find <industry> companies in <city>" (with or without a URL). One call
  discovers, researches and scores. Use it directly; never ask the user which source to use.
- lead_generation: other discovery — Google Places, curated sources, decision-makers, or
  researching companies by name. Pass the names and any URLs from the conversation.
- save_leads_tool: save confirmed leads to the user's Leads page (and ERPNext when configured).
  Use it for "add/save these leads", "add them to my CRM / pipeline".
- crm_management: read, update or analyze ERPNext records (optional integration).
- outreach: send email, check Google Calendar availability, create events.

Rules
- Read-only work (search, research, scoring) needs no permission.
- Writes (CRM records, emails, events) need the user's yes, and YOU ask for it — sub-agents
  cannot talk to the user. Never write right after find_leads_tool.
  1. User asks for a write: list exactly what will be written and ask "Shall I go ahead?".
  2. User confirms ("yes"): for leads call save_leads_tool ONCE with every lead's details
     copied from the conversation. For other writes call the sub-agent ONCE with "User
     confirmed." plus every detail it needs — it cannot see the chat.
  3. Report the sub-agent's result per item. Never ask the user to confirm twice.
- Sub-agent tools take one argument, input: a plain-language instruction, never JSON.
- Ask one question only when a required value is missing (no industry or city, no lead ID).
- Call a tool once per user message. If it returns nothing, report its notes; do not retry.
- Report only what tools returned. Never invent contacts, IDs, availability or confirmations.
  After save_leads_tool, state its `summary` exactly; list only leads in its `results`.
  reason "not_configured": name the integration to add in Settings. reason "search_blocked":
  relay its message.
- Resolve relative dates ("tomorrow") to YYYY-MM-DD from [Now] before calling a tool.
- Reply in the user's language (English, Urdu, Roman Urdu); keep names and IDs in English.

Lead results: table Company | Tier (score) | Phone | Email | Website | Rating | City | Source,
High then Medium then Low, '—' for missing, `outside_city` leads listed separately. One line on
why the top lead ranks first, then offer to add High/Medium leads to the CRM.

Format: markdown; tables for 4+ similar items, bullets otherwise. PKR, DD-MMM-YYYY, +92 phones.
End with **Next Best Action**.
"""


# Turn budgets. A turn is one model call; lead research is discover -> verify
# -> enrich -> report plus the odd retry, which overran the SDK default of 10
# and surfaced to users as "The agent could not complete your request".
ORCHESTRATOR_MAX_TURNS = 12
LEAD_GEN_MAX_TURNS = 16
CRM_MAX_TURNS = 12


def build_orchestrator(llm_cfg: ResolvedLLMConfig) -> Agent[AgentContext]:
    """Build the orchestrator and its sub-agents for one user, one run.

    All four agents share the caller's single configured model. The old
    heavy/medium/light tiering is gone with the global keys: a user
    configures one provider, so there is only one model to route to.
    """
    model = build_model(llm_cfg)
    model_settings = build_model_settings(llm_cfg)

    lead_gen_agent = Agent[AgentContext](
    name="LeadGenAgent",
    model=model,
    model_settings=model_settings,
    instructions=(
        "You find and research companies. Searching and reading pages is read-only: never ask the\n"
        "user for a source, a URL or contact details — find them.\n"
        "- 'Find <industry> in <city>': find_leads_tool once (pass any URL the user gave).\n"
        "- Named companies: research_companies_tool once with all of them (max 8), passing any known\n"
        "  website or profile_url.\n"
        "- A URL: scrape_page_tool. On a directory, re-scrape with its `filters` as query parameters\n"
        "  (?industry=X&location=Y) and research its `listings` (url = profile_url).\n"
        "- Google Places: search_leads_multi_tool (ratings, phones); get_place_details_tool for a\n"
        "  website. Curated pages: search_source_sites_tool. Decision-makers: dork_search_tool.\n"
        "- reason 'not_configured': skip that source and mention it in one line.\n"
        "- At most 4 tool calls. When a tool's notes explain an empty result, that is the answer.\n"
        "Scoring: keep each company's score and tier; adjust by up to 15 for fit and say why.\n"
        "city_match false: list as outside the city. Places-only: High = rating >= 4.0, >= 100 reviews,\n"
        "phone and website; Medium = rating >= 3.5 or >= 50 reviews; else Low.\n"
        "Report only tool data with a source URL per lead; never invent companies or contacts.\n"
        "Output: Company | Tier (score) | Phone | Email | Website | Rating | City | Source.\n"
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
        "You operate the user's ERPNext CRM (optional; the app's own leads live in its database).\n"
        "Every call is real. You cannot talk to the user: the assistant calling you has already\n"
        "confirmed any write with them. NEVER ask for confirmation — act on the instruction.\n"
        "- Create: create_erpnext_lead_tool once per lead in the instruction (first_name = company\n"
        "  name, mobile_no = first phone, email_id = first email, '' when unknown). Missing contact\n"
        "  details are not a reason to stop.\n"
        "- read_erpnext_lead_tool(lead_id): an ID like CRM-LEAD-2026-00042, not a company name; find it\n"
        "  with analyze_crm_data_tool first.\n"
        "- update_erpnext_lead_tool: only passed fields change. Statuses: Lead, Open, Replied,\n"
        "  Opportunity, Quotation, Lost Quotation, Interested, Converted, Do Not Contact.\n"
        "- analyze_crm_data_tool lists raw records: count them yourself, say how many you examined, and\n"
        "  warn that the view may be truncated when the count equals limit.\n"
        "reason 'not_configured': ERPNext is not set up; point to Settings -> Integrations. Never claim\n"
        "success or invent an ID when a tool failed.\n"
        "Reply with one line per lead: created (returned lead ID) or failed (the error).\n"
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
        "You send email and manage the user's real Google Calendar. Every call is live.\n"
        "You cannot talk to the user: the assistant calling you has already confirmed any send or\n"
        "booking with them. Never ask for confirmation — act on the instruction and report.\n"
        "- Email: send_email_tool with a clear subject and call to action.\n"
        "- Scheduling: check_availability_tool(date=YYYY-MM-DD) first, then create_event_tool\n"
        "  (times YYYY-MM-DDTHH:MM:SS with no Z or offset; end defaults to start + 1h; Asia/Karachi).\n"
        "  Confirm with the event's title, time, attendees and html_link.\n"
        "- On an error or missing credentials, report it exactly (calendar: connect Google Calendar in\n"
        "  Settings). Never invent availability, event IDs, links or confirmations.\n"
    ),
    tools=[send_email_tool, check_availability_tool, create_event_tool],
    )

    return Agent[AgentContext](
        name="SalesOpsOrchestrator",
        model=model,
        model_settings=model_settings,
        instructions=SALES_AGENT_SYSTEM_PROMPT,
        tools=[
            find_leads_tool,
            save_leads_tool,
            lead_gen_agent.as_tool(
                tool_name="lead_generation",
                tool_description=(
                    "Discovery beyond find_leads: Google Places, curated sources, decision-makers, "
                    "or researching named companies. Pass names, city and any URLs."
                ),
                max_turns=LEAD_GEN_MAX_TURNS,
                # Let LLM-provider errors (429, timeouts) end the run so chat.py
                # can report them. Swallowed into a tool error, they made the
                # orchestrator re-run the whole search — tripling token spend
                # against the very rate limit that caused the failure.
                failure_error_function=None,
            ),
            crm_agent.as_tool(
                tool_name="crm_management",
                tool_description=(
                    "Create, read, update or analyze ERPNext CRM leads. It cannot see the chat: "
                    "for creates pass 'User confirmed.' and one line per lead: "
                    "name | phone | email | website."
                ),
                # One create call per lead: 8 leads + the reply overruns the default 10.
                max_turns=CRM_MAX_TURNS,
                failure_error_function=None,
            ),
            outreach_agent.as_tool(
                tool_name="outreach",
                tool_description="Send email, check calendar availability, create calendar events.",
                failure_error_function=None,
            ),
        ],
    )


# ── Helper: build full prompt from message history ───────────────────────

from datetime import datetime

# The whole history is re-sent on every model call of every agent, so it is
# the fastest-growing cost. Old lead tables are the bulk of it and rarely matter.
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CHARS = 1200
# Except the latest assistant reply: a follow-up like "yes" or "add them" acts
# on its details (names, phones, emails). Clipping it made the agent pass
# "Phone etc." to the CRM and stall in a confirmation loop.
LATEST_REPLY_CHARS = 6000


def _get_current_datetime_context() -> str:
    """One line the agents use to resolve 'tomorrow' and friends."""
    return f"[Now] {datetime.now().strftime('%A, %Y-%m-%d %I:%M %p')}"


def _field(msg, name: str) -> str:
    return msg.get(name, "") if isinstance(msg, dict) else getattr(msg, name, "")


def _build_input(messages: list[dict]) -> str:
    """Recent conversation + the current request as one prompt string.

    System messages are dropped: the system prompt is already the agent's
    instructions, and echoing it here sent it twice on every call.
    """
    turns = [(_field(m, "role"), _field(m, "content")) for m in messages]
    turns = [(r, c) for r, c in turns if r in ("user", "assistant")]
    if not turns:
        return _get_current_datetime_context()

    *earlier, (last_role, last_content) = turns
    request = last_content if last_role == "user" else ""
    if last_role != "user":
        earlier.append((last_role, last_content))

    recent = earlier[-MAX_HISTORY_MESSAGES:]
    latest_reply = max(
        (i for i, (role, _) in enumerate(recent) if role == "assistant"), default=-1
    )

    def clip(i: int, content: str) -> str:
        limit = LATEST_REPLY_CHARS if i == latest_reply else MAX_HISTORY_CHARS
        return content[:limit] + (" …" if len(content) > limit else "")

    history = "\n".join(f"{role}: {clip(i, content)}" for i, (role, content) in enumerate(recent))
    parts = [f"Conversation so far:\n{history}"] if history else []
    parts += [_get_current_datetime_context(), f"User: {request}"]
    return "\n\n".join(parts)


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
    user_id: str | None = None,
    google_refresh_token: str | None = None,
    integrations: dict | None = None,
) -> str:
    """Run the agent orchestration loop (non-streaming)."""
    token = current_run_id.set(run_id)
    creds = integrations or {}
    try:
        context = AgentContext(
            run_id=run_id or "",
            user_id=user_id,
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
    user_id: str | None = None,
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
            user_id=user_id,
            google_refresh_token=google_refresh_token,
            erpnext=creds.get("erpnext"),
            google_places=creds.get("google_places"),
            google_calendar=creds.get("google_calendar"),
            lead_sources=creds.get("lead_sources"),
            google_dork_search=creds.get("google_dork_search"),
        )
        logger.info("Agent run started for run_id=%s", run_id)

        # Not run_streamed: Vercel buffers the response anyway, and the SDK
        # refuses to retry a streamed call once any chunk has arrived — so a
        # malformed tool call from a small model (Groq "tool_use_failed") failed
        # the whole chat. A non-streamed call is retried by build_model_settings.
        result = await Runner.run(
            starting_agent=build_orchestrator(llm_config),
            input=_build_input(messages),
            context=context,
            max_turns=ORCHESTRATOR_MAX_TURNS,
        )

        last_agent = None
        for item in result.new_items:
            agent_name = getattr(getattr(item, "agent", None), "name", None)
            if agent_name and agent_name != last_agent:
                steps.append({"type": "agent", "agent": agent_name})
                last_agent = agent_name

            if item.type == "tool_call_item":
                current_tool_name = getattr(getattr(item, "raw_item", None), "name", "unknown")
                logger.info("Tool call: %s (run=%s)", current_tool_name, run_id)
                steps.append({"type": "tool_start", "tool": current_tool_name})
            elif item.type == "tool_call_output_item":
                steps.append({
                    "type": "tool_result",
                    "tool": current_tool_name,
                    "content": str(item.output)[:500],
                })

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


