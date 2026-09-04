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

from core.config import settings
from agent_core.tracing import DatabaseTracingProcessor, current_run_id, flush_pending_writes

logger = logging.getLogger(__name__)

# ── Tracing ──────────────────────────────────────────────────────────────

set_trace_processors([DatabaseTracingProcessor()])

# ── Model factory ────────────────────────────────────────────────────────


def _make_model(api_key: str, base_url: str, model_name: str):
    """Create an OpenAI-compatible model instance."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


# Gemini tiers
model_heavy = _make_model(
    settings.GEMINI_API_KEY,
    settings.GEMINI_BASE_URL,
    settings.GEMINI_MODEL_HEAVY,
)
model_medium = _make_model(
    settings.GEMINI_API_KEY,
    settings.GEMINI_BASE_URL,
    settings.GEMINI_MODEL_MEDIUM,
)

# OpenRouter (CRM agent) — falls back to Gemini light if no key is set
if settings.OPENROUTER_API_KEY:
    model_openrouter = _make_model(
        settings.OPENROUTER_API_KEY,
        settings.OPENROUTER_BASE_URL,
        settings.OPENROUTER_MODEL,
    )
    logger.info("CRM agent using OpenRouter: %s", settings.OPENROUTER_MODEL)
else:
    model_openrouter = _make_model(
        settings.GEMINI_API_KEY,
        settings.GEMINI_BASE_URL,
        settings.GEMINI_MODEL_LIGHT,
    )
    logger.info(
        "No OPENROUTER_API_KEY — CRM agent falling back to %s",
        settings.GEMINI_MODEL_LIGHT,
    )


# ── Agent Context ────────────────────────────────────────────────────────

from dataclasses import dataclass


@dataclass
class AgentContext:
    run_id: str
    google_refresh_token: str | None = None


# ── Tool wrappers ────────────────────────────────────────────────────────

from mcp_tools.erpnext import (
    create_erpnext_lead, read_erpnext_lead, update_erpnext_lead,
    analyze_crm_data, get_chatbot_link,
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


async def _call(tool_name: str, arguments: dict, context: AgentContext = None) -> dict:
    """Route a tool-call request to the correct MCP tool implementation."""
    try:
        logger.info("Executing tool: %s", tool_name)
        # Inject context-aware tokens if needed
        if tool_name in ["check_availability", "create_event"] and context:
            arguments["refresh_token"] = context.google_refresh_token

        match tool_name:
            case "create_erpnext_lead":
                return await create_erpnext_lead(CreateLeadInput(**arguments))
            case "read_erpnext_lead":
                return await read_erpnext_lead(ReadLeadInput(**arguments))
            case "update_erpnext_lead":
                return await update_erpnext_lead(UpdateLeadInput(**arguments))
            case "analyze_crm_data":
                return await analyze_crm_data(AnalyzeCrmInput(**arguments))
            case "get_chatbot_link":
                return await get_chatbot_link(arguments["lead_id"])
            case "send_email":
                return await send_email(
                    arguments["to_email"], arguments["subject"],
                    arguments["body"],
                )
            case "search_businesses":
                return await search_businesses(SearchBusinessesInput(**arguments))
            case "search_leads_multi":
                return await search_leads_multi(SearchLeadsMultiInput(**arguments))
            case "get_place_details":
                return await get_place_details(GetPlaceDetailsInput(**arguments))
            case "check_availability":
                return await check_availability(CheckAvailabilityInput(**arguments))
            case "create_event":
                return await create_event(CreateEventInput(**arguments))
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
    simulation_mode: bool = True,
) -> dict:
    """Creates a lead in ERPNext CRM with optional quotation line items."""
    return await _call("create_erpnext_lead", {
        "first_name": first_name, "mobile_no": mobile_no,
        "email_id": email_id, "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def read_erpnext_lead_tool(
    wrapper: RunContextWrapper[AgentContext],
    lead_id: str, simulation_mode: bool = True,
) -> dict:
    """Retrieves lead details from ERPNext CRM by Lead ID."""
    return await _call("read_erpnext_lead", {
        "lead_id": lead_id, "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def update_erpnext_lead_tool(
    wrapper: RunContextWrapper[AgentContext],
    lead_id: str, status: str = None, lead_name: str = None,
    notes: str = None, phone: str = None, email_id: str = None,
    simulation_mode: bool = True,
) -> dict:
    """Updates an existing lead in ERPNext CRM."""
    return await _call("update_erpnext_lead", {
        "lead_id": lead_id, "status": status, "lead_name": lead_name,
        "notes": notes, "phone": phone, "email_id": email_id,
        "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def analyze_crm_data_tool(
    wrapper: RunContextWrapper[AgentContext],
    doctype: str = "Lead", limit: int = 20,
    simulation_mode: bool = True,
) -> dict:
    """Fetches and summarises CRM data from ERPNext."""
    return await _call("analyze_crm_data", {
        "doctype": doctype, "limit": limit, "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def get_chatbot_link_tool(
    wrapper: RunContextWrapper[AgentContext], lead_id: str,
) -> dict:
    """Fetches the quotation / chatbot link for a given Lead ID."""
    return await _call("get_chatbot_link", {"lead_id": lead_id}, context=wrapper.context)


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
    query: str, max_results: int = 20, simulation_mode: bool = True,
) -> dict:
    """Search for businesses using Google Places."""
    return await _call("search_businesses", {
        "query": query, "max_results": max_results,
        "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def search_leads_multi_tool(
    wrapper: RunContextWrapper[AgentContext],
    industry: str, location: str,
    max_results_per_query: int = 10, simulation_mode: bool = True,
) -> dict:
    """Primary lead discovery tool with parallel search + dedup."""
    return await _call("search_leads_multi", {
        "industry": industry, "location": location,
        "max_results_per_query": max_results_per_query,
        "simulation_mode": simulation_mode,
    }, context=wrapper.context)


@function_tool
async def get_place_details_tool(
    wrapper: RunContextWrapper[AgentContext],
    place_id: str, simulation_mode: bool = True,
) -> dict:
    """Fetch detailed information about a place by Google Place ID."""
    return await _call("get_place_details", {
        "place_id": place_id, "simulation_mode": simulation_mode,
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


# ── Sub-agents (each with its own model tier) ────────────────────────────

lead_gen_agent = Agent[AgentContext](
    name="LeadGenAgent",
    model=model_medium,  # gemini-2.5-flash
    model_settings=ModelSettings(include_usage=True),
    instructions=(
        "You are a specialized Lead Generation Agent. Your job is to discover and enrich potential business leads.\n\n"
        "## Search Strategy\n"
        "1. Use `search_leads_multi_tool` for broad discovery based on industry and location.\n"
        "2. Use `search_businesses_tool` for targeted single-query searches when the user is specific.\n"
        "3. Enrich top prospects using `get_place_details_tool` to gather phone, website, and address.\n\n"
        "## Opportunity Scoring\n"
        "Assign an opportunity score (High / Medium / Low) to each lead based on:\n"
        "- **High**: Rating ≥ 4.0, review count ≥ 100, has website and phone.\n"
        "- **Medium**: Rating ≥ 3.5 OR review count ≥ 50, has at least one contact method.\n"
        "- **Low**: Everything else.\n\n"
        "## Output Rules\n"
        "- NEVER use markdown tables. Present each lead as a bold-titled bullet list.\n"
        "- Format: **Lead Name** followed by indented details (address, rating, phone, website, opportunity score).\n"
        "- Group leads by opportunity score: High first, then Medium, then Low.\n"
        "- Always suggest which leads the user should add to their CRM and offer to do it for them.\n"
    ),
    tools=[search_leads_multi_tool, search_businesses_tool, get_place_details_tool],
)

crm_agent = Agent[AgentContext](
    name="CRMAgent",
    model=model_openrouter,  # OpenRouter z-ai/glm-4.5-air:free (or Gemini-lite fallback)
    model_settings=ModelSettings(include_usage=True),
    instructions=(
        "You are a specialized CRM Management Agent operating ERPNext.\n\n"
        "## Core Capabilities\n"
        "1. Create leads using `create_erpnext_lead_tool`.\n"
        "2. Update existing leads with `update_erpnext_lead_tool`.\n"
        "3. Read lead details with `read_erpnext_lead_tool`.\n"
        "4. Analyze pipeline health and insights with `analyze_crm_data_tool`.\n"
        "5. Generate chatbot links with `get_chatbot_link_tool`.\n\n"
        "## Output Rules\n"
        "- NEVER use markdown tables. Use bold headings and bullet points.\n"
        "- When listing leads, present each as: **Lead Name** — Status: X, Source: Y, Created: Z.\n"
        "- When showing pipeline analysis, use bold labels: **Open**: 18, **Replied**: 10, etc.\n"
        "- After creating or updating a lead, confirm the action with the lead ID and key details.\n"
        "- Proactively suggest next actions (e.g., 'Would you like to schedule a follow-up?').\n"
    ),
    tools=[
        create_erpnext_lead_tool, read_erpnext_lead_tool,
        update_erpnext_lead_tool, analyze_crm_data_tool, get_chatbot_link_tool,
    ],
)

outreach_agent = Agent[AgentContext](
    name="OutreachAgent",
    model=model_medium,  # gemini-2.5-flash
    model_settings=ModelSettings(include_usage=True),
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
        "- NEVER use markdown tables. Use bold headings and bullet points.\n"
        "- Always confirm actions with REAL data from tool responses.\n"
        "- NEVER invent event IDs, calendar links, or time slots.\n"
    ),
    tools=[send_email_tool, check_availability_tool, create_event_tool],
)

SALES_AGENT_SYSTEM_PROMPT = """\
Role: SalesOps Orchestrator — autonomous lead-gen specialist + ERPNext CRM operator.

You manage specialized agents:
- lead_generation: Discover and enrich leads from Google Places.
- crm_management: Manage and analyze CRM data in ERPNext.
- outreach: Draft emails, check REAL Google Calendar availability, and create REAL calendar events.

# Strategy
1. Delegate broad lead discovery requests to `lead_generation`.
2. Delegate CRM tasks (creating/reading/updating leads, pipeline analysis) to `crm_management`.
3. Delegate ALL scheduling, meeting, availability, and email tasks to `outreach`. This agent has access to the user's real Google Calendar — it is NOT a simulation.
4. When leads are discovered, proactively ask the user which ones they want to add to the CRM, then delegate to `crm_management`.
5. After adding leads to the CRM, suggest next steps like scheduling a follow-up call or sending an introductory email.

# Lead Workflow
- When showing discovered leads, assign an **Opportunity Score** (High / Medium / Low) based on rating, reviews, and contact availability.
- Group leads by score: **High Opportunity** first, then **Medium**, then **Low**.
- Always ask: "Would you like me to add any of these leads to your CRM? You can filter by score or pick specific ones."
- When adding leads to CRM, extract: name, email, phone, and source (Google Places).

# Ambiguity Protocol
IF intent unclear OR missing params (industry, city, lead-ID):
  → Ask ONE targeted clarification question. Do NOT guess or hallucinate parameters.

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
- **NEVER** use markdown tables (no | --- | syntax). Instead:
  - Use **bold headings** for categories.
  - Use bullet points (- or •) for listing items.
  - Use indented sub-bullets for details under each item.
- Example format for leads:
  **Al-Shifa Clinic** (Opportunity: High)
  - Address: 45-A, Main Boulevard, Gulberg III, Lahore
  - Rating: 4.5 ⭐ (230 reviews)
  - Phone: +92-42-35761234
  - Website: alshifaclinic.pk
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

orchestrator_agent = Agent[AgentContext](
    name="SalesOpsOrchestrator",
    model=model_heavy,  # gemini-2.5-pro — complex multi-step reasoning
    model_settings=ModelSettings(include_usage=True),
    instructions=SALES_AGENT_SYSTEM_PROMPT,
    tools=[
        lead_gen_agent.as_tool(
            tool_name="lead_generation",
            tool_description="Discover and enrich leads",
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
    run_id: str | None = None,
    google_refresh_token: str | None = None,
) -> str:
    """Run the agent orchestration loop (non-streaming)."""
    token = current_run_id.set(run_id)
    try:
        context = AgentContext(
            run_id=run_id or "",
            google_refresh_token=google_refresh_token
        )
        result = await Runner.run(
            starting_agent=orchestrator_agent,
            input=_build_input(messages),
            context=context,
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
    run_id: str | None = None,
    google_refresh_token: str | None = None,
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

    try:
        context = AgentContext(
            run_id=run_id or "",
            google_refresh_token=google_refresh_token,
        )
        result = Runner.run_streamed(
            starting_agent=orchestrator_agent,
            input=_build_input(messages),
            context=context,
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


