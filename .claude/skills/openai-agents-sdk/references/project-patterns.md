# Project Patterns (agent-service/)

Conventions for adding agents to this repo's FastAPI service. Read alongside
`AGENTS.md`, which is the authority — this file covers the SDK-facing slice.

---

## Layout

```
agent-service/app/
├── main.py            FastAPI app; service-token dep; router registration
├── config.py          Settings (secrets/connection only) + DEFAULT_* code defaults
├── providers.py       build_model_from_settings — the ONLY AsyncOpenAI construction
├── crypto.py          AES-256-GCM port, byte-compatible with lib/social-crypto.ts
├── db.py              asyncpg pool + fetch helpers
├── agents/            One module per agent: instructions, parse, normalize, run
├── routes/            One router per domain; thin — no LLM logic
├── email_pipeline.py  Shared orchestration reused by the route and the worker
└── mailbox/           Stage 2 IMAP IDLE worker (optional, always-on hosting only)
```

**Agents hold LLM logic. Routes hold I/O and policy.** A route that builds prompts
is in the wrong layer.

---

## Trust model

```
Browser ─x─> agent-service          (never — no public surface)
Browser ───> Next.js /api/*  ───>  agent-service
             session auth          X-Service-Token
             clinicId from session
```

- Every non-`/health` route requires `X-Service-Token`, enforced as a router-level
  `Depends(require_service_token)` in `main.py`
- `AI_AGENT_SERVICE_TOKEN` and `AI_AGENT_BACKEND_URL` are server-only. Never
  `NEXT_PUBLIC_*`, never imported into a `'use client'` module
- `lib/agent-client.ts` is the only Next.js module that calls the service
- Next.js proxies re-derive `clinicId` from the session and never trust the body

---

## Configuration split

| Kind | Where | Examples |
|------|-------|----------|
| Secrets / connection | Env | `DATABASE_URL`, `SOCIAL_TOKEN_ENCRYPTION_KEY`, `AI_AGENT_SERVICE_TOKEN` |
| Operational | Env | `MAILBOX_WORKER_ENABLED`, `MAILBOX_IDLE_TIMEOUT_SECONDS` |
| **AI tuning** | **DB (`ai_settings`)** | `base_url`, `model`, `temperature`, `max_transcript_chars`, `enabled`, `auto_draft_enabled`, `requests_per_minute` |
| Code defaults | `config.py` | `DEFAULT_MODEL`, `DEFAULT_TEMPERATURE`, `DEFAULT_MAX_*` |

Never read AI tuning from env. `DEFAULT_*` applies only when the DB column is null:

```python
temperature = settings_row["temperature"]
temperature = DEFAULT_TEMPERATURE if temperature is None else float(temperature)
max_chars = settings_row["max_transcript_chars"] or DEFAULT_MAX_TRANSCRIPT_CHARS
```

Note the two idioms: `is None` for numerics (0.0 is valid), `or` for the cap.

---

## Agent module template

```python
"""<Name> agent: <input> -> <output> (OpenAI Agents SDK).

Uses prompt-instructed JSON + manual parse instead of output_type / json_schema
for compatibility with Groq and other OpenAI-compatible providers that only
support json_object mode.
"""
from __future__ import annotations

import json
import logging
import re

from agents import (
    Agent, ModelSettings, OpenAIChatCompletionsModel, Runner,
    set_default_openai_api, set_tracing_disabled,
)
from pydantic import BaseModel

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

logger = logging.getLogger("agent.<name>")


class <Name>Data(BaseModel):
    ...


class <Name>Result(BaseModel):
    data: <Name>Data
    total_tokens: int


INSTRUCTIONS = (...)          # enumerate JSON keys + allowed values; no fences


def _extract_json(text: str) -> dict: ...
def _normalize(parsed: dict) -> <Name>Data: ...


async def run_<name>(
    model: OpenAIChatCompletionsModel,
    input_text: str,
    temperature: float,
    max_output_tokens: int,
) -> <Name>Result:
    agent = Agent(
        name="<Human readable>",
        instructions=INSTRUCTIONS,
        model=model,
        model_settings=ModelSettings(temperature=temperature, max_tokens=max_output_tokens),
    )
    result = await Runner.run(agent, input_text, max_turns=1)
    usage = result.context_wrapper.usage
    data = _normalize(_extract_json(str(result.final_output or "{}")))
    return <Name>Result(data=data, total_tokens=usage.total_tokens)
```

The two `set_*` calls belong at **module import**, before any agent is built.
They are process-global and idempotent, so repeating them per module is fine.

---

## Route template

```python
@router.post("/<path>", response_model=<Name>Response)
async def handler(req: <Name>Request) -> <Name>Response:
    settings_row = await fetch_ai_settings(req.clinicId)
    if not settings_row or not settings_row["enabled"]:
        return <Name>Response(reason="ai_disabled")

    model = build_model_from_settings(settings_row)
    if model is None:
        return <Name>Response(reason="no_api_key")

    rows = await fetch_input(req.clinicId, req.id)
    if not rows:
        return <Name>Response(reason="no_input")

    temperature = settings_row["temperature"]
    temperature = DEFAULT_TEMPERATURE if temperature is None else float(temperature)

    try:
        result = await run_<name>(model, text, temperature, DEFAULT_MAX_OUTPUT_TOKENS)
    except Exception:  # noqa: BLE001 - never leak provider errors to the caller
        logger.exception("<name> agent failed for %s", req.id)
        return <Name>Response(reason="agent_error")

    logger.info("<name> %s | tokens=%s", req.id, result.total_tokens)
    return <Name>Response(...)
```

Guard order is deliberate — cheapest and most common exits first: kill switch, then
missing key, then missing input, then the model call.

### The `reason` contract

Failures return `reason` with a null payload. They never raise past the route.
Callers (`lib/agent-client.ts`) treat a null payload as "fall back" — the heuristic
summary, or no suggestion — so an AI outage degrades instead of breaking the flow.

Reasons in use: `ai_disabled`, `no_api_key`, `no_transcript` / `no_input`,
`agent_error`.

Register the router in `main.py`:

```python
app.include_router(<name>.router, dependencies=[Depends(require_service_token)])
```

---

## Rate limiting and pacing

- `ai_settings.requests_per_minute` paces background drafting; `rpmDelayMs` in
  `lib/email-draft-runner.ts` is the shared implementation
- The cron path is bounded: ≤10 clinics, ≤5 emails each, ≤50 s per run
- Manually triggered endpoints are rate-limited in Next.js (`lib/rate-limit.ts`),
  not in the agent service — e.g. `/api/inbox/ai-suggest` at 15/min/clinic

Background work is paced. Human-initiated work is rate-limited. Do not apply the
background heuristic pre-filter to a manual single-click path — the filter exists
to protect the unattended worker from volume, and it would surprise a user who
explicitly asked for a suggestion.

---

## Deployment notes

- Vercel: `agent-service/api/index.py` + `vercel.json` (`@vercel/python`). The
  rewrite is required because FastAPI routes mount at root (`/health`, `/summarize`,
  `/email/draft`), not under `/api`
- Serverless pool must be `min_size=0`
- `MAILBOX_WORKER_ENABLED` must stay false on Vercel — IDLE needs a live process.
  Auto-draft on Vercel runs through `app/api/cron/auto-draft` instead
- `crypto.py` is byte-compatible with `lib/social-crypto.ts`. Changing either
  means changing both — otherwise every stored key fails to decrypt
- Full steps: `docs/deployment.md`

---

## After changing anything

```bash
npm run typecheck   # zero errors
npm run lint        # zero errors (react-hooks v6 warnings acceptable)
npm run build       # must succeed
```

Update `AGENTS.md` in the same change when an endpoint, env var, or auth behavior
changes.
