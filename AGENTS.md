# AGENTS.md — QuerySales AI

**This file is the authority on architecture, process, and project memory.**
Where any other rules file disagrees with this one, this file wins.

Read this file first, every session, before touching code.

---

## 1. What this project is

**QuerySales AI** — an autonomous AI sales employee that understands company knowledge,
analyzes leads, reasons about opportunities, plans sales actions, and executes CRM/outreach
actions using tools.

The demo that must work end-to-end:

```
Knowledge → RAG → Agent Reasoning → Planning → Tool Calling → Sales Action → Trace/Logs
```

Source of requirements: [plan.md](plan.md). It is the specification. This file is how we execute it.

Time budget is short (~12 working hours). **Optimize for a working, visible, end-to-end demo —
not for production scale.**

---

## 2. Repository map

```text
AISeekho-challenge/
├── AGENTS.md                    ← you are here (authority + memory)
├── plan.md                      ← the product specification (do not edit)
├── README.md                    ← public project README (legacy: describes the RN-era system)
├── docs/
│   ├── IMPLEMENTATION_PLAN.md   ← phase-by-phase build plan
│   ├── REUSE_MAP.md             ← EXISTING → REUSE / ADAPT / BUILD audit
│   └── summery/                 ← one summary file per completed phase (MANDATORY)
├── salesops-agent-backend/      ← FastAPI + OpenAI Agents SDK. THE backend. Reuse it.
│   ├── agent_core/              ←   orchestrator.py (chat agents), tracing.py (DB tracing)
│   ├── api/endpoints/           ←   route handlers
│   ├── core/                    ←   config.py (pydantic settings), security.py (JWT + crypto)
│   ├── db/                      ←   models.py (SQLAlchemy), session.py (async engine)
│   ├── mcp_tools/               ←   erpnext.py, gmail.py, google_places.py, google_calendar.py
│   ├── alembic/                 ←   migrations
│   └── main.py                  ←   FastAPI entrypoint
├── salesopsapp/                 ← React Native app. REFERENCE ONLY. Do not build on it.
└── querysales-web/              ← Next.js dashboard. DOES NOT EXIST YET — Phase 7 creates it.
```

### Architecture

```text
Browser
   │  authenticated request (Neon Auth JWT)
   ▼
Next.js (querysales-web)  ── server-side fetch ──►  FastAPI (salesops-agent-backend)
                                                          │  authenticated user_id
                                        ┌─────────────────┼─────────────────┐
                                        ▼                 ▼                 ▼
                                  User Config        RAG / pgvector    Sales Agent
                                  (LLM/Embed/Email)  (docs + chunks)   (tools + tracing)
                                        └─────────────────┼─────────────────┘
                                                          ▼
                                              Neon PostgreSQL + pgvector
                                              user-scoped rows, encrypted secrets
```

---

## 3. Hard rules

These are not preferences. Breaking one of these is a bug.

### 3.1 Reuse before you build
The FastAPI backend, its auth, its DB session, its agent orchestrator, its tracing processor and
its MCP tools already work. **Do not rewrite them.** Extend them. Before adding anything, check
[docs/REUSE_MAP.md](docs/REUSE_MAP.md) for whether an equivalent already exists.

### 3.2 Every row is user-scoped
Every user-owned record carries `user_id`: leads, knowledge documents, knowledge chunks, agent
runs, outreach drafts, all configuration.

- Derive `user_id` **only** from `Depends(get_current_user)`. Never from a query param, path
  param, or request body.
- Every `SELECT`/`UPDATE`/`DELETE` on a user-owned table filters `WHERE user_id = <authenticated>`.
- Vector similarity search filters by `user_id` **inside** the SQL, not after fetching.
- A 404 (not a 403) is the correct response when a row exists but belongs to another user.

### 3.3 Secrets never leave the server
- API keys, OAuth tokens, SMTP passwords are stored **encrypted** (AES-256-GCM) and decrypted
  only server-side, at the moment of use.
- The encryption key comes from the `ENCRYPTION_KEY` env var. It is **never** stored in Postgres.
- Settings responses return `{ "configured": true, "masked": "sk-••••1234" }` — never the secret.
- No secret ever reaches `NEXT_PUBLIC_*`, browser JavaScript, an agent trace, or a log line.
- Never log: API keys, access/refresh tokens, `Authorization` headers, DB passwords,
  `ENCRYPTION_KEY`, or raw email bodies containing customer PII.

### 3.4 No global LLM client
Configuration is **per user**. The agent resolves LLM, embedding, and email configuration from
the authenticated user's rows at run time. Module-level singleton model clients built from global
env vars are forbidden in new code (`agent_core/orchestrator.py` currently does this for the chat
agents — see the Phase 4 refactor).

### 3.5 Errors are handled, never leaked
- Route handlers catch, log the real cause server-side with context, and return a generic message.
  `main.py` already has global handlers — match that pattern.
- Every UI operation has four states: **Loading · Success · Error · Empty**.
- No silent failures. A degraded path returns a `reason` the caller can act on.

### 3.6 Do not overengineer
Do not build: multi-agent swarms, WhatsApp, voice/calling, LinkedIn, Google Places expansion,
enterprise RBAC, billing, teams, Kubernetes, event-driven infrastructure, or the mobile app.
If a feature threatens the core demo, simplify it, push it to P1/P2, and keep moving.

### 3.7 The React Native app is read-only
`salesopsapp/` is a design and API-usage reference. Extract concepts (`theme.ts` palette,
`WorkflowTimeline.tsx`, `GlassCard.tsx`, `RunLogCard.tsx`, `MetricCard.tsx`). **Never** edit it,
and never copy React Native code verbatim into the web app.

---

## 4. Code conventions

### Backend (Python / FastAPI)
- Route handlers stay thin: **validate → authorize → call a service/tool module → shape response.**
- Data access lives in `db/` and dedicated service modules, never inline in a route body.
- All DB access is async (`AsyncSession`); use the `get_db` dependency.
- Pydantic models for every request and response body. No bare `dict` responses on new endpoints.
- `except Exception as exc:` — never a bare `except:`. Log with `exc_info=True`.
- Schema changes go through Alembic: edit `db/models.py`, `alembic revision --autogenerate`,
  **read the generated SQL**, then `alembic upgrade head`. Never hand-write DDL into app code.
- New third-party packages go in `pyproject.toml` (direct deps only). Then
  `uv lock` and `uv export --no-dev --no-hashes --no-annotate --no-emit-project
  --format requirements-txt -o requirements.txt`. Vercel's `@vercel/python`
  builder installs from `requirements.txt`, not `pyproject.toml`.
- Module names are `snake_case`; tools live in `mcp_tools/`, agent logic in `agent_core/`.

### Frontend (Next.js / TypeScript / Tailwind)
- App Router. **Server components by default**; `'use client'` only for interactivity, kept at
  the leaf.
- `params` and `searchParams` are `Promise` — type them as such and `await` them.
- Files are **kebab-case** (`lead-detail-client.tsx`); React components inside are `PascalCase`.
- A client component that pairs with a server page is suffixed `-client`.
- **Never use `any`.** `strict` is on.
- The browser talks to Next.js route handlers / server components; those talk to FastAPI. The
  session JWT lives in an httpOnly cookie, never in `localStorage`.
- Extract a shared component the second time the same UI appears.

### Both
- Comment the **why**, not the what.
- No magic numbers, no deep nesting, prefer early returns.
- Soft size guidance: React component < 300 lines · service module < 500 · route handler < 200.

---

## 5. Phase workflow — MANDATORY

Work proceeds phase by phase through [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

**At the start of a phase**
1. Re-read this file's §7 Project Memory and §8 Decision Log.
2. Re-read the phase's section in `docs/IMPLEMENTATION_PLAN.md`.
3. Confirm the previous phase's summary exists in `docs/summery/`.

**At the end of every phase — before starting the next one**

1. **Write the phase summary** to `docs/summery/phase-<N>-<kebab-slug>.md`, using the template at
   [docs/summery/_TEMPLATE.md](docs/summery/_TEMPLATE.md). The summary is not optional and is not
   deferred to the end of the project. A phase is not complete until its summary is written.

   The summary must record:
   - what was built, as a list of files created/modified with one line each on why
   - what was verified, and **how** (the exact command run and its actual result)
   - what was deliberately deferred or simplified, and to which priority (P1/P2)
   - decisions made, with rationale
   - anything discovered that changes a later phase
   - known gaps / follow-ups

2. **Update this file's memory** (§7 Project Memory, §8 Decision Log, §9 Phase Status). This is
   the durable, always-loaded context. `docs/summery/` is the detailed archive; §7–§9 here is the
   index a future session reads first.
   - Add a line to §9 Phase Status.
   - Add any new architectural decision to §8 Decision Log.
   - Add anything non-obvious a future session needs to §7 Project Memory. Do **not** record what
     the code already says — record what the code cannot tell you (why a value was chosen, what a
     provider actually does, what broke and why).

3. **Verify before claiming done.** Run the phase's acceptance checks. Report failures honestly
   with output. Never mark a phase complete on the basis of "it should work".

**Never** skip a phase summary to save time. The summary *is* the handoff.

---

## 6. Commands

```bash
# ── Backend (from salesops-agent-backend/) ────────────────────────────────
uvicorn main:app --reload --port 8000     # run API      → http://localhost:8000/docs
alembic revision --autogenerate -m "msg"  # generate migration (READ IT before applying)
alembic upgrade head                      # apply migrations
alembic downgrade -1                      # roll back one
python -m scripts.seed_demo               # seed demo users/leads/knowledge  (Phase 6)

# ── Frontend (from querysales-web/) ───────────────────────────────────────
npm run dev            # dev server → http://localhost:3000
npm run lint           # zero errors
npm run build          # authoritative type gate — MUST pass before a phase is done
```

`npm run build` catches page/route type errors that `tsc --noEmit` cannot see. A clean typecheck
does not mean the app compiles.

### Environment

Backend `.env` (see `salesops-agent-backend/.env.example`):
`DATABASE_URL`, `ENCRYPTION_KEY`, `NEON_AUTH_URL`, `NEON_AUTH_JWKS_URL`, `ERPNEXT_BASE_URL`,
`ERPNEXT_API_TOKEN`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, plus optional system-fallback
`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `EMBEDDING_*`.

Frontend `.env.local`: `NEXT_PUBLIC_APP_URL`, `API_URL` (server-only), `NEON_AUTH_URL`.

**Never commit real keys.** `.env.example` carries placeholder values only.

---

## 7. Project Memory

> Durable facts a future session cannot derive from the code. Append here at every phase end.
> Convert relative dates to absolute. Delete entries that turn out to be wrong.

- **2026-09-04 — Baseline audit.** The repo at hand-over contains a working FastAPI backend
  (chat orchestrator, tracing, ERPNext/Gmail/Places/Calendar tools, Neon Auth JWT) and a React
  Native app. It contains **no** leads table, **no** knowledge/RAG layer, **no** pgvector,
  **no** per-user configuration, and **no** web frontend. Full detail in
  [docs/REUSE_MAP.md](docs/REUSE_MAP.md).

- **Auth is Neon Auth (Better Auth), not a local password table.** There is no
  `POST /auth/login` in the backend and there should not be one. The client authenticates
  directly against `NEON_AUTH_URL/sign-in/email`, then exchanges the session token for a JWT at
  `NEON_AUTH_URL/token`. The backend verifies that JWT against `NEON_AUTH_JWKS_URL` via JWKS
  (EdDSA) in `core/security.py:get_current_user`, and upserts the user row on first sight.
  `salesopsapp/src/services/authService.ts` is the working reference implementation.

- **`openai-agents` was missing from `requirements.txt`.** Fixed in Phase 0 —
  `requirements.txt` is now exported from `uv.lock` (direct deps declared in
  `pyproject.toml`). Any new dependency: add to `pyproject.toml`, `uv lock`,
  `uv export … -o requirements.txt`.

- **The existing crypto helper is Fernet, not AES-256-GCM.** `core/security.py` exposes
  `encrypt_token` / `decrypt_token` backed by `cryptography.fernet.Fernet` (AES-128-CBC + HMAC),
  used today only for `users.google_refresh_token`. plan.md §45 requires AES-256-GCM for the new
  per-user credential columns. Keep the Fernet path for the legacy column; do not retrofit it.

- **`.claude/rules/code-style.md` and `.agents/rules/code-style.md` were stale**
  and described a different repository. Rewritten in Phase 0 to describe this
  repo (FastAPI + Next.js). They must stay byte-identical; both defer to this file.

- **Git initialised** with baseline commit `d1ef5f8` (2026-09-04). Commit after
  every phase boundary. `.gitignore` covers `.env`, `.venv/`, `node_modules/`,
  `.next/`, `.mypy_cache/`, `__pycache__/`.

- **Vercel's Python runtime buffers responses**, so true SSE streaming is impossible on the
  deployed backend. `run_orchestrator_with_events` exists precisely because of this: it collects
  every agent/tool event during the run and returns them as one JSON body. The live-timeline UI
  must therefore be built on **polling `GET /api/runs/{id}/events`**, not on an event stream.

- **`WorkflowStep` (`workflow_steps` table) is defined but unused** by any code path. Leave it
  alone; do not build on it.

- **`uv` manages the Python environment.** `.venv/` is created by `uv sync`; run
  Python via `.venv/Scripts/Activate.ps1` (PowerShell) or `uv run python`.
  `pyproject.toml` declares direct deps only; `uv.lock` resolves the full tree;
  `requirements.txt` is the lock export for Vercel. All three must stay in sync.

- **One `ENCRYPTION_KEY` serves both Fernet and AES-256-GCM.** A Fernet key is
  url-safe-base64(32 bytes) which is exactly the 256-bit key `AESGCM` needs.
  Phase 2's `core/crypto.py` decodes with `base64.urlsafe_b64decode`. Losing the
  key makes every stored credential permanently unrecoverable.

- **Neon console `DATABASE_URL` uses `postgresql://` (sync) and appends
  `channel_binding=require` (libpq-only).** Both break asyncpg. `db/session.py`
  normalises automatically: swaps scheme to `postgresql+asyncpg://`, renames
  `sslmode` → `ssl`, and strips `channel_binding` / `gssencmode` / `krbsrvname`
  / `gsslib`. Alembic does its own swap in `alembic/env.py`.

- **pgvector 0.8.6 is live** on the Neon branch (enabled 2026-09-04).

- **Gemini embeddings need explicit `dimensions=1536`** (default is 3072).
  Phase 3's `embed.py` must pass `dimensions=1536` when calling the OpenAI-compatible
  embeddings endpoint. Decision D2 fixes the column at `vector(1536)`.

---

## 8. Decision Log

> Architectural choices and their rationale. Append; do not rewrite history.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Keep the existing 3-sub-agent chat orchestrator **as-is**; build the autonomous lead analyst as a **new, separate single agent** in `agent_core/sales_agent.py`. | plan.md §34 mandates one main agent + tools for the demo. The chat orchestrator already works and is demoable; rewriting it burns hours and risks regression. Two entrypoints, one shared tracing layer. |
| D2 | Fix the pgvector embedding column at **`vector(1536)`**. | plan.md §8 requires the stored dimension to match the model and forbids silent changes. 1536 is the dimension of `text-embedding-3-small` and most OpenAI-compatible endpoints. The user's configured `dimension` is validated against 1536 on save and rejected with a clear message if it differs. Documented, not silent. |
| D3 | Per-user credentials use **AES-256-GCM** via `cryptography`'s `AESGCM`, in a new `core/crypto.py`. Legacy `users.google_refresh_token` keeps Fernet. | plan.md §45 asks for AES-256-GCM explicitly. Migrating the one legacy column is not worth the demo time. |
| D4 | The browser never calls FastAPI directly. The session JWT lives in an **httpOnly cookie**; Next.js server components and route handlers attach it as a Bearer token server-side. | Keeps the token out of browser JS, satisfies plan.md §30, and gives one place to handle 401s. Costs one extra hop, which is irrelevant at demo scale. |
| D5 | Leads live in **our Postgres**, user-scoped — not in ERPNext. ERPNext stays an optional *outbound* tool (create opportunity / push lead). | plan.md §49 requires per-user lead isolation, which a single shared ERPNext instance cannot provide. It also removes ERPNext availability as a demo blocker. |
| D6 | The live analysis timeline is driven by **polling** `GET /api/runs/{id}/events`, not SSE. | Vercel's Python runtime buffers responses (see §7). Polling works identically locally and deployed. |
| D7 | **One `ENCRYPTION_KEY`** serves both Fernet (legacy) and AES-256-GCM (new `core/crypto.py`). | A Fernet key is url-safe-base64(32 bytes), which is exactly the 256-bit key AESGCM needs. One key, one failure mode. Losing it makes every stored credential permanently unrecoverable. |
| D8 | `requirements.txt` is **exported from `uv.lock`**, never hand-maintained. | Vercel's `@vercel/python` builder reads `requirements.txt`. Lock-export guarantees local == deployed and prevents the drift that caused the missing `openai-agents` crash. |

---

## 9. Phase Status

> Update at the end of every phase. `Summary` links the file in `docs/summery/`.

| Phase | Name | Status | Summary |
|-------|------|--------|---------|
| 0 | Audit, foundation & environment | ✅ Complete | [phase-0-foundation.md](summery/phase-0-foundation.md) |
| 1 | Data model & migrations | ⬜ Not started | — |
| 2 | Per-user config, crypto & settings API | ⬜ Not started | — |
| 3 | RAG pipeline & knowledge API | ⬜ Not started | — |
| 4 | Autonomous sales agent & tools | ⬜ Not started | — |
| 5 | Leads, analyze & run/trace APIs | ⬜ Not started | — |
| 6 | Demo seed data | ⬜ Not started | — |
| 7 | Next.js scaffold, auth & app shell | ⬜ Not started | — |
| 8 | Dashboard, leads & live analysis UI | ⬜ Not started | — |
| 9 | Knowledge, run detail & settings UI | ⬜ Not started | — |
| 10 | Isolation verification, E2E demo & polish | ⬜ Not started | — |

Legend: ⬜ Not started · 🟨 In progress · ✅ Complete · ⚠️ Complete with known gaps

---

## 10. Definition of done

The project is complete when all of the following hold (plan.md §37, §60):

**Core flow**
- [ ] Login → Dashboard → Lead → *Analyze with QuerySales AI* → agent starts
- [ ] Agent calls `search_knowledge`; pgvector returns real, user-scoped chunks
- [ ] Agent qualifies the lead and calls `update_lead`; the lead row actually changes
- [ ] Agent generates personalized outreach; the user can approve / create a draft
- [ ] The run timeline shows every phase and every tool call

**Multi-user**
- [ ] Two users can log in; each sees only their own leads, knowledge, runs, settings
- [ ] Each user has independent LLM / embedding / email configuration
- [ ] User A cannot read User B's data or use User B's credentials through any request

**Security**
- [ ] Credentials encrypted at rest with AES-256-GCM; key outside the database
- [ ] Secrets never in frontend responses, never in logs, never in agent traces

**Quality**
- [ ] `alembic upgrade head` clean · FastAPI starts · `npm run build` passes
- [ ] Loading / success / error / empty states on every major operation
- [ ] Demo data seeded — the dashboard never opens empty
