# Reuse Map — EXISTING → REUSE / ADAPT / BUILD

Required by [plan.md](../plan.md) §35. This is the audit of what the repository already contains,
decided against what QuerySales AI needs. Consult it before writing any new module.

Audit date: **2026-09-04** · Repo: `AISeekho-challenge` (not under git)

Legend — **REUSE**: use as-is · **ADAPT**: extend in place · **BUILD**: does not exist

---

## 1. Backend infrastructure

| Existing | Location | Verdict | Notes |
|---|---|---|---|
| FastAPI app, CORS, global exception + validation handlers, `/health` | `salesops-agent-backend/main.py` | **REUSE** | Error handlers already log server-side with a correlation id and return a generic body. Match this pattern in new routes. |
| Async SQLAlchemy engine, Neon pool hardening, `get_db` dependency | `db/session.py` | **REUSE** | `pool_pre_ping`, `pool_recycle=270`, `pool_size=2` are tuned for Neon + serverless. Do not change. |
| Alembic wired to `Base.metadata`, asyncpg→psycopg2 swap for DDL | `alembic/env.py`, `alembic.ini` | **REUSE** | Autogenerate works. 3 migrations applied. |
| Pydantic `Settings` from `.env` | `core/config.py` | **ADAPT** | Add `LLM_*` / `EMBEDDING_*` optional system-fallback vars (plan §54 Option B). Existing provider vars stay for the chat orchestrator. |
| Vercel serverless config | `vercel.json` | **REUSE** | — |

## 2. Authentication & crypto

| Existing | Location | Verdict | Notes |
|---|---|---|---|
| Neon Auth (Better Auth) JWT verification via JWKS, EdDSA/ES256/RS256, user upsert on first login | `core/security.py:get_current_user` | **REUSE** | This is *the* auth dependency. Every new user-scoped route depends on it. |
| Client-side sign-in / sign-up / session-token→JWT exchange | `salesopsapp/src/services/authService.ts` | **REFERENCE** | Port the flow to Next.js verbatim in logic, not in code. `POST {NEON_AUTH_URL}/sign-in/email` → `GET {NEON_AUTH_URL}/token`. |
| Role gate `get_sales_manager` | `core/security.py` | **REUSE (unused)** | plan §6 says no complex RBAC. Leave it; do not extend it. |
| Fernet `encrypt_token` / `decrypt_token` | `core/security.py` | **REUSE for legacy only** | Backs `users.google_refresh_token`. New per-user credentials use AES-256-GCM (Decision D3). |
| AES-256-GCM helper | — | **BUILD** | New `core/crypto.py`. plan §45. |

## 3. Database models

| Existing | Location | Verdict | Notes |
|---|---|---|---|
| `User` (id, email, role, google_refresh_token, google_calendar_connected) | `db/models.py` | **REUSE** | Id is the Neon Auth `sub`. Ownership anchor for everything new. |
| `WorkflowRun` (id, user_id, status, mode, workflow_type) | `db/models.py` | **ADAPT** | Add `lead_id`, `final_result` (JSON), `completed_at`. This becomes plan §6's `agent_runs` — no second table. |
| `ToolCallLog` (run_id, tool_name, input/output JSON, error, duration_ms) | `db/models.py` | **REUSE** | Already exactly what the run-detail timeline needs for `TOOL_CALL` events. |
| `AuditTrace` (run_id, agent_name, thought_process, tokens, cost) | `db/models.py` | **REUSE** | Backs `REASON`/`PLAN` events. |
| `ChatMessageLog` | `db/models.py` | **REUSE** | Chat history. Untouched by the new flow. |
| `WorkflowStep` | `db/models.py` | **IGNORE** | Defined but referenced by no code path. Do not build on it. |
| `Lead` | — | **BUILD** | plan §6. User-scoped, local. Decision D5. |
| `KnowledgeDocument`, `KnowledgeChunk` | — | **BUILD** | plan §6, §50. `embedding vector(1536)`. |
| `UserLLMConfig`, `UserEmbeddingConfig`, `UserEmailConfig` | — | **BUILD** | plan §41–44. |
| `AgentEvent` (semantic phases) | — | **BUILD** | plan §6 `agent_events`: OBSERVE / RETRIEVE / REASON / PLAN / TOOL_CALL / RESULT / COMPLETE. The existing traces are *span*-typed, not *phase*-typed — see §7 below. |
| `OutreachDraft` | — | **BUILD** | plan §20 approve-and-send. |
| pgvector extension | — | **BUILD** | `CREATE EXTENSION IF NOT EXISTS vector;` + `pgvector` Python package. |

## 4. Agent layer

| Existing | Location | Verdict | Notes |
|---|---|---|---|
| OpenAI Agents SDK orchestrator: `SalesOpsOrchestrator` + `LeadGenAgent` / `CRMAgent` / `OutreachAgent` as tools | `agent_core/orchestrator.py` | **REUSE as the chat agent** | Works today. Keep the chat surface. Decision D1. |
| `_make_model()` — OpenAI-compatible model factory (`AsyncOpenAI` + `OpenAIChatCompletionsModel`) | `agent_core/orchestrator.py:40` | **ADAPT** | Exactly the right shape for per-user providers. The problem is *where* it is called: module import time, from global settings. Lift into a per-run factory. |
| Module-level `model_heavy` / `model_medium` / `model_openrouter` singletons | `agent_core/orchestrator.py:47-75` | **ADAPT — this is the key refactor** | Violates §3.4 (no global LLM client). Agents must be constructed per run from the authenticated user's config. |
| `AgentContext` dataclass (run_id, google_refresh_token) | `agent_core/orchestrator.py:83` | **ADAPT** | Add `user_id`, `lead_id`, resolved config handles. The `RunContextWrapper` plumbing already reaches every tool. |
| `run_orchestrator_with_events()` — collects agent/tool events into a structured response | `agent_core/orchestrator.py:601` | **REFERENCE** | The pattern to copy for the sales agent. Note *why* it exists: Vercel buffers responses, so SSE is impossible. |
| `DatabaseTracingProcessor` — SDK spans → `ToolCallLog` + `AuditTrace`, with a pending-write flush | `agent_core/tracing.py` | **REUSE + ADAPT** | Reuse wholesale. Add an `AgentEvent` emitter alongside it so the UI gets semantic phases, not raw spans. `flush_pending_writes()` before returning is mandatory on serverless. |
| Token/cost estimation, `MODEL_PRICING` | `agent_core/tracing.py:56` | **REUSE** | Extend the map when new models appear; unknown models return `None` cost, which is fine. |
| Single autonomous sales agent (`OBSERVE→…→COMPLETE`) | — | **BUILD** | New `agent_core/sales_agent.py`. plan §12, §34. |

## 5. Agent tools

| Existing | Location | Verdict | Notes |
|---|---|---|---|
| ERPNext create / read / update lead, `analyze_crm_data`, `get_chatbot_link` | `mcp_tools/erpnext.py` | **REUSE (optional path)** | plan §13 Tool 4 "reuse if stable". Uses a single global API token — it cannot be user-scoped, so it is an *outbound* convenience only, never the source of truth for leads. Must degrade gracefully when unconfigured. |
| Gmail SMTP `send_email` | `mcp_tools/gmail.py` | **ADAPT** | Currently one global `GMAIL_USER` / `GMAIL_APP_PASSWORD`. Needs a per-user SMTP config path (plan §44). Draft-first, send only on approval (plan §13 Tool 6). |
| Google Places `search_businesses` / `search_leads_multi` / `get_place_details` | `mcp_tools/google_places.py` | **KEEP, DO NOT EXTEND** | plan §3 puts Places out of scope. Leave it wired to the chat agent only. |
| Google Calendar `check_availability` / `create_event` | `mcp_tools/google_calendar.py` | **KEEP, DO NOT EXTEND** | plan §3 puts Calendar out of scope for the new flow. |
| `search_knowledge(query)` | — | **BUILD** | plan §11. The single most important new tool — the agent must *decide* to call it. |
| `get_lead` / `update_lead` (local, user-scoped) | — | **BUILD** | plan §13 Tools 2 & 3. |
| `draft_outreach` | — | **BUILD** | plan §13 Tool 5. |

## 6. API endpoints

| plan.md §28 wants | Existing equivalent | Verdict |
|---|---|---|
| `POST /auth/login` | — (Neon Auth handles it externally) | **NOT NEEDED** — do not build. See AGENTS.md §7. |
| `GET /dashboard/stats` | `GET /api/dashboard/stats` — `api/endpoints/dashboard.py` | **ADAPT** — currently ERPNext pipeline + local usage. Re-point at local user-scoped leads, add knowledge-document and qualified-lead counts. |
| `GET /leads`, `GET /leads/{id}`, `PATCH /leads/{id}` | `GET /api/dashboard/leads` (ERPNext-backed, not user-scoped) | **BUILD** — new `api/endpoints/leads.py` over the local table. |
| `POST /leads/{id}/analyze` | — | **BUILD** |
| `GET /knowledge`, `POST /knowledge/upload`, `POST /knowledge/{id}/process`, `DELETE /knowledge/{id}`, `POST /knowledge/search` | — | **BUILD** — new `api/endpoints/knowledge.py`. |
| `GET /runs`, `GET /runs/{id}` | `GET /api/runs`, `GET /api/runs/{run_id}` — `api/endpoints/runs.py` | **REUSE + ADAPT** — already user-scoped with ownership checks. Add lead/score/qualification to the response and a new `GET /api/runs/{id}/events`. |
| run timeline / trace | `GET /api/workflows/{run_id}/logs` — `api/endpoints/logs.py` | **ADAPT** — merges `ToolCallLog` + `AuditTrace` into a sorted timeline with an ownership check. Extend to emit semantic phases. |
| `GET/PUT /settings/llm`, `/settings/embedding`, `+ /test` | — | **BUILD** — new `api/endpoints/settings.py`. |
| Chat | `POST /api/chat`, `/stream`, `GET /history` | **REUSE** — untouched. |
| Calendar | `api/endpoints/calendar.py` | **KEEP** — out of scope. |

## 7. Known gap: span-typed traces vs. phase-typed events

`DatabaseTracingProcessor` records what the *SDK* did — `function`, `agent`, `generation`,
`handoff` spans. plan §6 and §20 need what the *business* did — `OBSERVE`, `RETRIEVE`, `REASON`,
`PLAN`, `TOOL_CALL`, `RESULT`, `COMPLETE`.

These are different taxonomies and one cannot be derived reliably from the other. The sales agent
must emit `AgentEvent` rows explicitly at each phase boundary, **in addition to** the automatic
span tracing. Do not try to reverse-engineer phases from span types.

## 8. Frontend

| Existing | Location | Verdict |
|---|---|---|
| Entire Next.js dashboard | — | **BUILD** — `querysales-web/` does not exist. |
| Aurora dark/light palette, spacing, radius, typography tokens | `salesopsapp/src/theme.ts` | **REFERENCE** — port to Tailwind CSS variables. Dark `#07111F` / surface `#0D1728` / primary `#6D5CFF` → `#885CF6` → `#36CFFF`. |
| `WorkflowTimeline.tsx`, `RunLogCard.tsx`, `GlassCard.tsx`, `MetricCard.tsx`, `AuroraGradient.tsx` | `salesopsapp/src/components/` | **REFERENCE** — recreate the *concepts* in React + Tailwind. Never copy RN code. |
| `OutcomeDashboardScreen`, `TraceLogsScreen`, `CRMLeadsScreen`, `SimulationConsoleScreen` | `salesopsapp/src/screens/` | **REFERENCE** — information architecture and terminology. |
| `httpClient.ts`, `runsApi.ts`, `dashboardApi.ts` | `salesopsapp/src/services/` | **REFERENCE** — existing API request/response shapes, saving guesswork. |

## 9. Dependencies to add

Backend — add to **both** `pyproject.toml` and `requirements.txt`:

| Package | Why |
|---|---|
| `openai-agents>=0.17.2` | **Already imported, already in `pyproject.toml`, missing from `requirements.txt`.** Deploys installing from requirements fail at import. |
| `pgvector` | SQLAlchemy `Vector` column type. |
| `pypdf` | PDF text extraction (plan §9 — secondary to TXT/MD). |

Frontend (`querysales-web/`): `next`, `react`, `typescript`, `tailwindcss`, `lucide-react`,
`recharts` (only if charts survive prioritisation).

## 10. Do not build (plan §3, §33)

WhatsApp · voice/calling · LinkedIn automation · Google Places expansion · Google Calendar
expansion · advanced scraping · enterprise RBAC · billing · teams · multi-agent swarm ·
Postgres full-text search (until pgvector RAG works) · Kubernetes · deployment automation ·
any further work on `salesopsapp/`.
