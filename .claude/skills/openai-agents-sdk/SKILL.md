---
name: openai-agents-sdk
description: |
  Build, configure, and debug agents written with the OpenAI Agents SDK for Python
  (openai-agents), including OpenAI-compatible third-party providers such as Groq,
  Gemini, OpenRouter, Azure, and local gateways.
  This skill should be used when working in `agent-service/`, adding or changing an
  agent, tool, or FastAPI agent route, wiring a new model provider or base_url,
  or diagnosing SDK failures — "400 Missing or invalid Authorization header",
  "Tracing client error 401", "OPENAI_API_KEY is not set", "response_format.type
  value is not one of the allowed values", MaxTurnsExceeded, or JSON that fails to
  parse out of final_output. Also use when asked about Agent, Runner,
  OpenAIChatCompletionsModel, ModelSettings, function_tool, handoffs, guardrails,
  sessions, or tracing configuration.
---

# OpenAI Agents SDK

Build and debug `openai-agents` (Python) agents, with first-class support for
non-OpenAI providers behind an OpenAI-compatible Chat Completions endpoint.

## What This Skill Does

- Scaffolds new agents, model wiring, and FastAPI agent routes that match this
  repo's `agent-service/` conventions
- Configures third-party providers (Groq, Gemini, OpenRouter, Azure, local) correctly
- Diagnoses the SDK's cryptic auth/tracing/structured-output failures
- Enforces the token-cost and trust-boundary rules this project depends on

## What This Skill Does NOT Do

- Write or run database migrations (see `migrations/` + `AGENTS.md`)
- Call the agent service from the browser — the Next.js BFF is the only caller
- Add send/write capability to an agent (agents draft text; **code** sends and persists)
- Choose the model or temperature — those are per-clinic DB config, never env vars

---

## Step 0 — Review Current Docs (Required)

The SDK moves fast and training data lags it. **Before writing or changing SDK
code, pull current documentation via the context7 MCP server.**

1. Resolve the library id: `mcp__context7__resolve-library-id` with
   `"OpenAI Agents SDK Python"`
2. Query the docs: `mcp__context7__query-docs` with id
   `/websites/openai_github_io_openai-agents-python` and a specific question
   (vague one-word queries return poor results)

CLI equivalent when MCP is unavailable:

```bash
npx ctx7@latest library "OpenAI Agents SDK Python" "<your question>"
npx ctx7@latest docs /websites/openai_github_io_openai-agents-python "<your question>"
```

Query with the real question, e.g. *"OpenAIChatCompletionsModel with non-OpenAI
provider, set_tracing_disabled, structured output json_schema support"*.
Max 3 context7 calls per question. Never put API keys in a query.

Alternate ids: `/openai/openai-agents-python` (repo + examples, version-pinnable
as `/openai/openai-agents-python/v0.7.0`).

**Do not silently fall back to memory.** If context7 fails (quota, network), say so,
then verify against the installed package with
`python -c "import agents; print(agents.__file__)"` and read the source under that path.

---

## Before Implementation

Gather context before writing code:

| Source | Gather |
|--------|--------|
| **Codebase** | `agent-service/app/agents/*.py` for agent shape; `providers.py` for model construction; `routes/*.py` for the request/response contract |
| **Context7 docs** | Current API surface for whatever primitive you are touching (Step 0) |
| **Conversation** | Which agent, which provider, what the failure symptom is |
| **Skill references** | `references/` below — provider setup, troubleshooting, structured output, repo conventions |
| **Project guidelines** | `AGENTS.md` — BFF rule, token-saving rules, "AI drafts, code sends" |

Only ask the user for **their** requirements. Domain knowledge lives in this skill.

---

## Core Pattern: Model Construction

Never hardcode a provider. Build the model from config and pass it to the `Agent`.

```python
from agents import (
    Agent, AsyncOpenAI, ModelSettings, OpenAIChatCompletionsModel, Runner,
    set_default_openai_api, set_tracing_disabled,
)

# Module import time, before any agent runs:
set_default_openai_api("chat_completions")  # not the Responses API
set_tracing_disabled(True)                  # non-OpenAI keys cannot auth to OpenAI tracing

client = AsyncOpenAI(api_key=api_key, base_url=base_url)   # base_url=None => real OpenAI
model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)

agent = Agent(
    name="Call summarizer",
    instructions=INSTRUCTIONS,
    model=model,
    model_settings=ModelSettings(temperature=temperature, max_tokens=max_output_tokens),
)
result = await Runner.run(agent, user_input, max_turns=1)
```

### Five rules that prevent most failures

1. **Import `AsyncOpenAI` from `agents`**, not from `openai`.
2. **`set_tracing_disabled(True)`** whenever the key is not a `platform.openai.com` key.
3. **`set_default_openai_api("chat_completions")`** — third-party providers do not
   implement the Responses API.
4. **Never set `os.environ["OPENAI_API_KEY"]`** to a non-OpenAI key. It misroutes auth.
5. **Never use `output_type=`** in this project — see structured output below.

In this repo, model construction already lives in
`agent-service/app/providers.py` (`build_model_from_settings`) and reads
per-clinic `ai_settings`. **Reuse it. Do not build a second client.**

Full initialization options, provider base_url values, tracing alternatives, and
mixed-provider setups: `references/provider-setup.md`

---

## Core Pattern: Structured Output

**Use prompt-instructed JSON + manual parsing. Never `output_type=`.**

Groq and several other OpenAI-compatible providers reject
`response_format: json_schema`, which is what `output_type` emits:

```text
BadRequestError: 400 - 'response_format.type' : value is not one of the
allowed values ['text','json_object']
```

The working shape (see `agent-service/app/agents/summary_agent.py`):

1. Spell the exact JSON keys and allowed values out in `instructions`
2. End instructions with "No markdown fences, no extra keys."
3. Parse with `_extract_json()` — strips fences, falls back to first `{...}` block
4. Run every field through `_normalize()` — coerce unknown enum values to a default
5. Validate the normalized dict into a Pydantic model

Never trust the model to obey the schema. Parsing and normalization are the contract.

Parser/normalizer code, vision (`input_image`) input, and the vision-400 text-only
fallback: `references/structured-output.md`

---

## Troubleshooting Fast Path

| Symptom | Cause | Fix |
|---------|-------|-----|
| `400 Missing or invalid Authorization header` | Non-OpenAI key + tracing enabled | `set_tracing_disabled(True)` before any agent init |
| `Tracing client error 401` / `OPENAI_API_KEY is not set, skipping trace export` | Same | Same |
| `response_format.type value is not one of the allowed values` | `output_type=` on a provider without json_schema | Drop `output_type`; use prompt-JSON |
| `404` on `/responses` | Responses API on a Chat-Completions-only provider | `set_default_openai_api("chat_completions")` |
| `AsyncOpenAI has no such method` | Imported from `openai` instead of `agents` | `from agents import AsyncOpenAI` |
| `ModuleNotFoundError: agents` | Package missing | `pip install openai-agents` (pinned `>=0.2`) |
| `MaxTurnsExceeded` | Model looping on tools | Raise `max_turns`, or `max_turns=1` for single-shot extraction |
| `json.JSONDecodeError` on `final_output` | Model wrapped JSON in prose/fences | Harden `_extract_json`; log `raw_head` |

The 400 masks a 401: the tracing exporter fails auth first, and the surfaced error
is misleading. Always check tracing before debugging the model call.

Diagnostic script — verifies a provider config end to end with one cheap call:

```bash
python .claude/skills/openai-agents-sdk/scripts/check_provider.py \
  --base-url https://api.groq.com/openai/v1 --model llama-3.3-70b-versatile
```

Reads `AGENT_TEST_API_KEY` (or `--api-key`). Full cause chains and decision tree:
`references/troubleshooting.md`

---

## Project Rules (agent-service/)

Non-negotiable in this repo — violating these breaks trust or cost boundaries:

- **BFF only.** The browser never reaches the agent service. Next.js route handlers
  call it with the server-only `AI_AGENT_SERVICE_TOKEN` via `lib/agent-client.ts`.
  Never expose that token as `NEXT_PUBLIC_*`.
- **The agent never writes the DB** on the summary/social paths — it returns text and
  Next.js persists. (The Stage 2 mailbox worker is the one deliberate exception.)
- **AI drafts; code sends.** No send tool, no send endpoint.
- **Tuning is per-clinic DB config**, not env: `model`, `temperature`,
  `max_transcript_chars` come from `ai_settings`. Code defaults in `config.py` apply
  only when the column is null.
- **Token discipline is mandatory**: heuristic pre-filter before the LLM, `max_turns=1`,
  explicit `max_tokens`, input caps, and the `ai_settings.enabled` kill switch.
- **Routes never leak provider errors.** Catch broadly, `logger.exception(...)`, and
  return a `reason` string so the caller falls back gracefully.
- **Re-derive `clinicId` from the session** in the Next.js proxy; never trust the body.

Route/agent scaffolding templates and the full convention list:
`references/project-patterns.md`

---

## Adding a New Agent — Checklist

- [ ] Reviewed current docs via context7 (Step 0)
- [ ] New module in `agent-service/app/agents/<name>_agent.py`
- [ ] `set_default_openai_api("chat_completions")` + `set_tracing_disabled(True)` at import
- [ ] Model comes from `build_model_from_settings` — no second `AsyncOpenAI`
- [ ] `ModelSettings(temperature=..., max_tokens=...)` set explicitly
- [ ] `max_turns=1` unless the agent genuinely needs tool loops
- [ ] Prompt-instructed JSON; **no `output_type`**
- [ ] `_extract_json` + `_normalize` + Pydantic validation
- [ ] Input truncated to a documented cap
- [ ] Token usage read from `result.context_wrapper.usage` and logged
- [ ] Route added in `app/routes/`, registered in `main.py` with `require_service_token`
- [ ] Route returns `reason=...` instead of raising on failure
- [ ] Corresponding Next.js proxy route re-derives `clinicId` from session
- [ ] `AGENTS.md` updated if an endpoint or env var changed

---

## Reference Files

| File | When to Read |
|------|--------------|
| `references/provider-setup.md` | Wiring a provider, base_url values, tracing options, mixing providers |
| `references/troubleshooting.md` | Any SDK error; cause chains and decision tree |
| `references/structured-output.md` | JSON extraction, normalization, vision input, fallbacks |
| `references/project-patterns.md` | Repo conventions, agent + route templates, trust model |

| Script | Purpose |
|--------|---------|
| `scripts/check_provider.py` | Verify a provider/base_url/model config with one cheap call |

## Official Sources

- Docs: https://openai.github.io/openai-agents-python
- Models & non-OpenAI providers: https://openai.github.io/openai-agents-python/models/
- Config: https://openai.github.io/openai-agents-python/config/
- Tracing: https://openai.github.io/openai-agents-python/tracing/
- Examples: https://github.com/openai/openai-agents-python/tree/main/examples
