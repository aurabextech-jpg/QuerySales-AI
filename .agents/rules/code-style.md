# Code Style — QuerySales AI

Conventions for **this** repository: a Python FastAPI + OpenAI Agents SDK backend
(`salesops-agent-backend/`) and a Next.js App Router dashboard (`querysales-web/`), sharing one
Neon Postgres database with pgvector.

**[`AGENTS.md`](../../AGENTS.md) is the authority** on architecture, hard rules, process and
project memory. This file covers day-to-day code style. Where they disagree, `AGENTS.md` wins.

> This project has **no** `src/` in the web app, no Drizzle, no `lib/*-db.ts` modules, no
> `agent-service/` directory and no `ResponseBuilder`. If you find yourself writing one of those,
> you are thinking of a different repository.

---

# Repository layout

```text
salesops-agent-backend/        ← THE backend. FastAPI, deployed to Vercel as one lambda.
├── main.py                    ←   app factory, CORS, global exception handlers, router wiring
├── api/endpoints/             ←   route handlers — thin, one module per resource
├── agent_core/                ←   orchestrator.py (chat), sales_agent.py, tracing.py, events.py
├── core/                      ←   config.py (pydantic settings), security.py (JWT), crypto.py
├── db/                        ←   models.py (SQLAlchemy declarative), session.py (async engine)
├── mcp_tools/                 ←   ERPNext, Gmail SMTP, Google Places, Google Calendar
├── services/                  ←   business logic (knowledge/ RAG pipeline lives here)
├── scripts/                   ←   seed_demo.py, get_google_token.py
└── alembic/                   ←   migrations; env.py uses the SYNC psycopg2 driver

querysales-web/                ← Next.js App Router dashboard. The browser's only backend.
salesopsapp/                   ← React Native app. FROZEN. Design/API reference only — never edit.
```

Flow: **Browser → Next.js server component / route handler → FastAPI → Neon Postgres.**
The browser never calls FastAPI directly (Decision D4).

---

# Backend — Python / FastAPI

## Dependencies

- **uv owns the environment.** `pyproject.toml` declares *direct* dependencies only; `uv lock`
  resolves the tree; `requirements.txt` is **exported from the lock**, never hand-edited:
  ```bash
  uv lock
  uv sync
  uv export --no-dev --no-hashes --no-annotate --no-emit-project --format requirements-txt -o requirements.txt
  ```
- Vercel's `@vercel/python` builder installs from `requirements.txt`, not from `pyproject.toml`.
  A package missing there is a cold-start `ImportError` in production and nothing locally. After
  adding a dependency, regenerate `requirements.txt` **and** commit `uv.lock`.
- Python 3.13. Vercel defaults to 3.12 unless `.python-version` says otherwise — keep that file.

## Route handlers

- Stay thin: **validate → authorize → call a service/tool module → shape the response.**
- Data access lives in `db/` and `services/`, never inline in a route body.
- Pydantic models for every request and response body. No bare `dict` responses on new endpoints.
- Always async: `db: AsyncSession = Depends(get_db)`. Never a sync session in a request path.

## Authorization and user scoping

- Derive `user_id` **only** from `Depends(get_current_user)`. Never from a query param, a path
  param, or the request body.
- Every `SELECT` / `UPDATE` / `DELETE` on a user-owned table filters `WHERE user_id = <authenticated>`.
- Vector similarity search filters by `user_id` **inside** the SQL, not after fetching.
- A row that exists but belongs to someone else is a **404**, not a 403 — 403 confirms existence.

## Errors

- `except Exception as exc:` — never a bare `except:`. Log with `exc_info=True`.
- Log the real cause server-side; return a generic, actionable message to the client. `main.py`
  already has the global handlers — match that pattern rather than adding per-route try/except soup.
- Configuration problems are a **400 with an actionable message**, never a 500
  ("Configure your LLM provider in Settings → AI / LLM").
- A degraded optional path (ERPNext unreachable, email not configured) returns a `reason` the
  caller can act on. It never raises and never blocks the response.

## Secrets

- Encrypt with `core/crypto.py` (AES-256-GCM). The legacy `users.google_refresh_token` column
  keeps Fernet via `core/security.py` — do not retrofit it (Decision D3).
- The key comes from the `ENCRYPTION_KEY` env var and is **never** stored in Postgres.
- Settings responses return `{"configured": true, "masked": "sk-••••1234"}` — never the secret.
- Never log or trace: API keys, access/refresh tokens, `Authorization` headers, DB passwords,
  `ENCRYPTION_KEY`, or raw email bodies containing customer PII.

## Schema changes

Edit `db/models.py` → `alembic revision --autogenerate -m "msg"` → **read the generated SQL** →
`alembic upgrade head`. Never hand-write DDL into application code. Autogenerate does not
understand `pgvector` types; expect to fix the `Vector(1536)` import and column by hand, and write
a real `downgrade()`.

`metadata` is reserved by SQLAlchemy's declarative API — name JSON columns `chunk_metadata`,
`payload`, etc.

---

# Serverless constraints (Vercel)

These are not style preferences; violating them breaks the deployed demo.

- **Responses are buffered.** True SSE streaming is impossible. Live progress is driven by
  **polling** `GET /api/runs/{id}/events?after_sequence=N` (Decision D6).
- **Fire-and-forget tasks are cancelled** the moment the response returns. Anything that must be
  persisted uses the pending-write + `flush_pending_writes()` discipline from `agent_core/tracing.py`.
- **No module-level clients built from global env vars** for per-user resources (rule §3.4).
  Resolve LLM / embedding / email config from the authenticated user's rows **per run**.
- Keep the lambda small. Do not add a dependency without checking that it is actually imported.
- One lambda is single-concurrency: keep the SQLAlchemy pool tiny (`pool_size=2, max_overflow=3`),
  `pool_pre_ping=True`, `pool_recycle=270` (Neon closes idle connections at ~300s).

---

# Frontend — Next.js / TypeScript / Tailwind

- App Router. **Server components by default**; `'use client'` only for interactivity, kept at the
  leaf. A page needing one interactive widget renders a small client component; it does not become
  a client component itself.
- Server-only modules start with `import 'server-only';` so an accidental client import fails at
  build time. `lib/api-client.ts` is server-only and holds the JWT.
- `params` and `searchParams` are **`Promise`** — type them as such and `await` them.
- Files are **kebab-case** (`lead-detail-client.tsx`); React components inside are `PascalCase`.
  A client component that pairs with a server page is suffixed `-client`.
- **Never use `any`.** `strict` is on.
- The session JWT lives in an **httpOnly cookie**, never in `localStorage` and never readable from
  browser JS. `API_URL` is server-only and is **not** a `NEXT_PUBLIC_*` variable.
- Extract a shared component the second time the same UI appears. `components/ui/` holds only the
  primitives actually in use — do not add them speculatively.
- Every UI operation has four states: **Loading · Success · Error · Empty.** No silent failures,
  no infinite spinners. Polling clears its interval on unmount, on completion and on failure.
- Design language is ported from `salesopsapp/src/theme.ts` into Tailwind CSS variables. Extract
  concepts; **never copy React Native code verbatim** into the web app.

---

# Both

- Comment the **why**, not the what. A comment explaining a non-obvious constraint — a driver
  limitation, a provider quirk, a serverless behaviour — earns its place. Restating the code does not.
- No magic numbers, no deep nesting, prefer early returns.
- Soft size guidance: React component < 300 lines · service module < 500 · route handler < 200.
  Several existing files exceed this; refactor when you are already working in them, not as a
  side quest.
- Do not overengineer (rule §3.6). If a feature threatens the core demo, simplify it, push it to
  P1/P2 in `AGENTS.md`, and keep moving.

---

# Validation before done

```bash
# ── Backend (from salesops-agent-backend/) ────────────────────────────────
uv sync                                     # environment matches the lock
uv run alembic upgrade head                 # no pending migrations
uv run uvicorn main:app --reload --port 8000 # → http://localhost:8000/docs
uv run pytest                               # where tests exist

# ── Frontend (from querysales-web/) ───────────────────────────────────────
npm run lint    # zero errors
npm run build   # authoritative type gate — MUST pass before a phase is done
```

`npm run build` catches page and route type errors that `tsc --noEmit` cannot see, because `tsc`
does not include Next's generated `.next/types/**`. A clean typecheck does not mean the app compiles.

Never claim a phase is complete on the basis of "it should work". Run the acceptance checks in
`docs/IMPLEMENTATION_PLAN.md`, record the **exact command and its actual output** in
`docs/summery/`, and report failures honestly.
