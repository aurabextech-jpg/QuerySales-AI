# QuerySales AI — Phase-by-Phase Implementation Plan

Derived from [plan.md](../plan.md). Operating rules live in [AGENTS.md](../AGENTS.md).
The existing-code audit lives in [REUSE_MAP.md](REUSE_MAP.md).

**Every phase ends with a summary written to `docs/summery/phase-<N>-<slug>.md`.** See
[AGENTS.md §5](../AGENTS.md#5-phase-workflow--mandatory).

---

## Current state at a glance

| Layer | State |
|---|---|
| FastAPI app, CORS, error handling, `/health` | ✅ Working |
| Neon Auth JWT verification (JWKS/EdDSA) + user upsert | ✅ Working |
| Async SQLAlchemy + Neon pooling + Alembic (3 migrations) | ✅ Working |
| Chat orchestrator (OpenAI Agents SDK, 3 sub-agents, event collection) | ✅ Working |
| DB tracing processor (spans → `ToolCallLog` / `AuditTrace`, cost estimation) | ✅ Working |
| Tools: ERPNext, Gmail SMTP, Google Places, Google Calendar | ✅ Working |
| Endpoints: chat, runs, trace logs, dashboard stats, calendar | ✅ Working |
| React Native app | ✅ Working — **reference only, frozen** |
| **Leads table (local, user-scoped)** | ❌ Missing |
| **Knowledge documents + chunks** | ❌ Missing |
| **pgvector extension / embeddings / vector search** | ❌ Missing |
| **`search_knowledge` agent tool** | ❌ Missing |
| **Single autonomous sales agent** | ❌ Missing |
| **Semantic agent events (OBSERVE…COMPLETE)** | ❌ Missing |
| **Per-user LLM / embedding / email configuration** | ❌ Missing |
| **AES-256-GCM credential encryption** | ❌ Missing (Fernet exists, legacy only) |
| **Settings / knowledge / leads / analyze endpoints** | ❌ Missing |
| **Demo seed data** | ❌ Missing |
| **Next.js dashboard (`querysales-web/`)** | ❌ Missing entirely |

**Bottom line:** the backend *plumbing* is real and reusable; the backend *product* (RAG,
per-user config, the sales agent, leads) and the entire frontend are new work.

---

## Phase overview

| # | Phase | Budget | Blocks | Risk |
|---|---|---|---|---|
| 0 | Audit, foundation & environment | 0.5 h | everything | Low |
| 1 | Data model & migrations | 1.0 h | 2,3,4,5 | Medium — pgvector on Neon |
| 2 | Per-user config, crypto & settings API | 1.5 h | 3,4 | Low |
| 3 | RAG pipeline & knowledge API | 2.0 h | 4 | **High — the demo's core claim** |
| 4 | Autonomous sales agent & tools | 2.5 h | 5 | **High — per-user model refactor** |
| 5 | Leads, analyze & run/trace APIs | 1.5 h | 8,9 | Medium |
| 6 | Demo seed data | 0.5 h | 8,9,10 | Low |
| 7 | Next.js scaffold, auth & app shell | 1.5 h | 8,9 | Medium — Neon Auth in Next |
| 8 | Dashboard, leads & live analysis UI | 2.0 h | 10 | **High — the money screen** |
| 9 | Knowledge, run detail & settings UI | 1.5 h | 10 | Medium |
| 10 | Isolation verification, E2E demo & polish | 1.0 h | — | Medium |

Total ≈ **15.5 h** against a ~12 h budget. The overflow is deliberate: Phases 9–10 contain the
compressible work. If time runs short, cut in this order — charts → advanced filters → Gmail
send (keep draft) → PDF support (keep TXT/MD) → settings polish. **Never** cut Phases 3, 4, or 8.

---

# Phase 0 — Audit, foundation & environment

**Goal:** make the workspace honest and runnable before writing product code.
**Budget:** 0.5 h · **Depends on:** nothing

### Current state
Backend runs. Dependency manifests disagree. The auto-loading rules files describe a different
repository. No `docs/` content. Not a git repository.

### Tasks

1. **Fix the dependency manifests** — `salesops-agent-backend/requirements.txt`
   - Add `openai-agents>=0.17.2` (imported by `agent_core/orchestrator.py`, present only in
     `pyproject.toml` — installs from `requirements.txt` currently fail at import).
   - Add `pgvector` and `pypdf` to **both** `requirements.txt` and `pyproject.toml`.
2. **Rewrite the stale rules files** — `.claude/rules/code-style.md` and
   `.agents/rules/code-style.md` currently describe a Next.js 16 + Drizzle project with an
   `agent-service/` directory that does not exist here. Replace both with conventions matching
   this repo (they must agree; keep them byte-identical), and have them defer to `AGENTS.md`.
3. **Extend `.env.example`** — add the optional system-fallback keys `LLM_BASE_URL`,
   `LLM_API_KEY`, `LLM_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`,
   `EMBEDDING_DIMENSION`. Placeholders only, never real keys.
4. **Generate and set `ENCRYPTION_KEY`** — 32 random bytes, base64-encoded, in `.env` only.
5. **Verify the Neon connection and enable pgvector**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   SELECT extversion FROM pg_extension WHERE extname = 'vector';
   ```
6. **Confirm the baseline runs** — `alembic upgrade head`, then `uvicorn main:app --reload`,
   then `GET /health` returns `{"status":"healthy"}`.
7. **Decide the frontend location** — `querysales-web/` at the repo root, sibling to
   `salesops-agent-backend/` (plan §15).

### Acceptance
- [ ] `pip install -r requirements.txt` in a clean env, then `python -c "import agents"` succeeds
- [ ] `alembic upgrade head` reports no pending migrations
- [ ] `/health` returns healthy
- [ ] `SELECT extversion …` returns a version — pgvector is live on the Neon branch
- [ ] Both `code-style.md` files describe *this* repo

### Risks
Neon free tier may need pgvector enabled per branch. If `CREATE EXTENSION` is refused, that is a
**hard blocker for Phase 3** — resolve it now, not later.

### Summary → `docs/summery/phase-0-foundation.md`

---

# Phase 1 — Data model & migrations

**Goal:** every table the product needs, user-scoped, in one reviewed migration.
**Budget:** 1.0 h · **Depends on:** 0

### Current state
`db/models.py` has `User`, `WorkflowRun`, `WorkflowStep` (unused), `ToolCallLog`, `AuditTrace`,
`ChatMessageLog`. No leads, no knowledge, no config, no semantic events.

### Tasks

1. **`Lead`** — `leads` (plan §6)
   `id, user_id (FK, indexed), name, company, email, industry, website, status, score,
   pain_points (JSON), notes, created_at, updated_at`
   Statuses: `New · Analyzing · Qualified · Nurture · Disqualified · Contacted`.
   Index `(user_id, status)` — every list query filters on both.

2. **`KnowledgeDocument`** — `knowledge_documents` (plan §6, §50)
   `id, user_id (FK, indexed), filename, title, file_type, content (Text), status, chunk_count,
   error_message, created_at, updated_at`
   Statuses: `uploaded · extracting · chunking · embedding · indexed · failed`.

3. **`KnowledgeChunk`** — `knowledge_chunks` (plan §6, §50)
   `id, document_id (FK), user_id (FK, indexed), content, chunk_index,
   embedding Vector(1536), chunk_metadata (JSON), created_at`
   - `user_id` is denormalised onto the chunk **on purpose** — vector search must filter by user
     inside the SQL without a join (plan §50).
   - `embedding` is fixed at 1536 dimensions (Decision D2). Document this in the model docstring.
   - `metadata` is reserved by SQLAlchemy's declarative API — name the column `chunk_metadata`.

4. **`UserLLMConfig`** — `user_llm_config` (plan §42)
   `id, user_id (FK, unique), provider_name, base_url, api_key_encrypted, model, temperature,
   max_tokens, created_at, updated_at`

5. **`UserEmbeddingConfig`** — `user_embedding_config` (plan §43)
   `id, user_id (FK, unique), provider_name, base_url, api_key_encrypted, model, dimension,
   created_at, updated_at`

6. **`UserEmailConfig`** — `user_email_config` (plan §44)
   `id, user_id (FK, unique), provider, email_address, smtp_host, smtp_port,
   smtp_password_encrypted, access_token_encrypted, refresh_token_encrypted, token_expiry,
   created_at, updated_at`

7. **`AgentEvent`** — `agent_events` (plan §6)
   `id, run_id (FK, indexed), user_id (FK, indexed), phase, title, detail (Text),
   payload (JSON), sequence, created_at`
   `phase` ∈ `OBSERVE · RETRIEVE · REASON · PLAN · TOOL_CALL · RESULT · COMPLETE · ERROR`.

8. **`OutreachDraft`** — `outreach_drafts`
   `id, user_id (FK, indexed), lead_id (FK), run_id (FK), subject, body, status, sent_at,
   created_at` — statuses `draft · approved · sent · failed`.

9. **Extend `WorkflowRun`** — add `lead_id` (FK, nullable), `final_result` (JSON, nullable),
   `completed_at` (DateTime, nullable). This *is* plan §6's `agent_runs`; do not create a second
   runs table.

10. **Migration** — `alembic revision --autogenerate -m "querysales core schema"`.
    Then **open the generated file and edit it**:
    - Prepend `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` as the first upgrade step.
    - Confirm autogenerate emitted `Vector(1536)` and imported `pgvector.sqlalchemy` — it often
      does not. Add the import and fix the column type by hand if needed.
    - Add the IVFFlat index for cosine similarity:
      ```sql
      CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
        ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
      ```
    - Write a real `downgrade()`.

11. `alembic upgrade head`.

### Acceptance
- [ ] Migration applies cleanly to the Neon branch
- [ ] `\d knowledge_chunks` shows `embedding | vector(1536)` and the ivfflat index
- [ ] `alembic downgrade -1 && alembic upgrade head` round-trips without error
- [ ] Every user-owned table has a `user_id` column with an index

### Risks
- Autogenerate mishandles `pgvector` types — **read the migration**, never apply blind.
- ivfflat on an empty table warns about list count; harmless at demo scale.

### Summary → `docs/summery/phase-1-data-model.md`

---

# Phase 2 — Per-user config, crypto & settings API

**Goal:** every user owns their own encrypted credentials, and the agent can resolve them.
**Budget:** 1.5 h · **Depends on:** 1

### Current state
Only global env-var credentials. `core/security.py` has Fernet helpers used solely for
`users.google_refresh_token`.

### Tasks

1. **`core/crypto.py`** — AES-256-GCM (plan §45, §46, Decision D3)
   ```python
   encrypt_secret(plaintext: str) -> str   # base64(nonce || ciphertext || tag)
   decrypt_secret(blob: str) -> str
   mask_secret(plaintext: str) -> str      # "sk-••••1234"
   ```
   - Key from `settings.ENCRYPTION_KEY` (base64, 32 bytes). Fail loudly at import if malformed —
     a silent fallback to plaintext storage would be a security bug.
   - Use `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. **No custom cryptography.**
   - Fresh random 12-byte nonce per encryption.

2. **`core/user_config.py`** — the resolution service (plan §52, §54)
   ```python
   async def resolve_llm_config(user_id, db) -> ResolvedLLMConfig
   async def resolve_embedding_config(user_id, db) -> ResolvedEmbeddingConfig
   async def resolve_email_config(user_id, db) -> ResolvedEmailConfig | None
   ```
   - Order: **user row → optional system fallback (env) → raise `ConfigurationMissing`.**
   - Never read another user's row. The `user_id` argument comes only from `get_current_user`.
   - Return decrypted values in a dataclass that never crosses a response boundary.
   - `ConfigurationMissing` maps to a 400 with an actionable message
     ("Configure your LLM provider in Settings → AI / LLM"), never a 500.

3. **`api/endpoints/settings.py`** (plan §22, §53, §55)
   | Method | Path | Behaviour |
   |---|---|---|
   | GET | `/api/settings/llm` | `{configured, provider_name, base_url, model, temperature, max_tokens, api_key_masked}` — **never the key** |
   | PUT | `/api/settings/llm` | Upsert; encrypt the key; an omitted key keeps the stored one |
   | POST | `/api/settings/llm/test` | Decrypt server-side, one minimal chat completion, return `{success, message}` only |
   | DELETE | `/api/settings/llm` | Remove the configuration |
   | GET/PUT/POST/DELETE | `/api/settings/embedding[...]` | Same shape. **`PUT` rejects `dimension != 1536`** with a clear message (Decision D2) |
   | GET/PUT/POST/DELETE | `/api/settings/email[...]` | Same shape; `test` = SMTP connect + auth, no send |
   | GET | `/api/settings/database` | `{postgres: "connected", pgvector: "enabled"}` — never the DSN |

4. **Register the router** in `main.py` under `/api/settings`.

5. **Extend `core/config.py`** with the optional system-fallback `LLM_*` / `EMBEDDING_*` vars.

### Acceptance
- [ ] Encrypt → decrypt round-trips; two encryptions of the same input differ (fresh nonce)
- [ ] `psql` shows the stored key as base64 ciphertext, never `sk-...`
- [ ] `GET /api/settings/llm` returns `configured: true` and a masked key, never the plaintext
- [ ] `POST /api/settings/llm/test` returns `{success: true}` against a real provider
- [ ] `PUT /api/settings/embedding` with `dimension: 768` returns 400 with an explanatory message
- [ ] User B's `GET /api/settings/llm` returns User B's row, never User A's
- [ ] No key appears in any log line — grep the captured server output

### Risks
Losing `ENCRYPTION_KEY` makes every stored credential unrecoverable. Note this in `.env.example`.

### Summary → `docs/summery/phase-2-user-config.md`

---

# Phase 3 — RAG pipeline & knowledge API

**Goal:** real documents in, real vectors out, real user-scoped similarity search.
**Budget:** 2.0 h · **Depends on:** 1, 2 · **Risk: HIGH — this is the demo's central claim**

### Current state
Nothing. No ingestion, no embeddings, no vector search.

### Tasks

1. **`services/knowledge/extract.py`** (plan §9, §10)
   - `.txt` / `.md` → decode UTF-8, replacement-on-error.
   - `.pdf` → `pypdf`. **Secondary priority** (plan §9): if it costs more than ~20 minutes, ship
     TXT/MD and move PDF to P1.
   - Validate before reading: extension allowlist `{.txt,.md,.pdf}`, max size **10 MB**, non-empty
     after extraction. Reject with 400 (plan §30).

2. **`services/knowledge/chunk.py`**
   - Clean: collapse whitespace, strip control characters, normalise newlines.
   - Chunk: ~1000 characters, ~150 overlap, split on paragraph then sentence boundaries.
   - Return `[{content, chunk_index, chunk_metadata: {title, filename, char_start}}]`.

3. **`services/knowledge/embed.py`**
   - `async def embed_texts(texts: list[str], cfg: ResolvedEmbeddingConfig) -> list[list[float]]`
   - `AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url).embeddings.create(...)` — the same
     OpenAI-compatible shape the orchestrator already uses for chat.
   - Batch ~64 inputs per request.
   - **Assert every returned vector has length 1536**; on mismatch raise with the actual vs.
     expected dimension. Never silently pad or truncate (plan §8).

4. **`services/knowledge/search.py`** — the retrieval half (plan §10, §50)
   ```sql
   SELECT c.id, c.content, c.chunk_index, c.chunk_metadata,
          d.title, d.filename,
          1 - (c.embedding <=> :query_embedding) AS similarity
     FROM knowledge_chunks c
     JOIN knowledge_documents d ON d.id = c.document_id
    WHERE c.user_id = :user_id          -- NON-NEGOTIABLE
    ORDER BY c.embedding <=> :query_embedding
    LIMIT :top_k                        -- default 5
   ```
   Returns `{document, chunk, similarity, metadata}` (plan §10).
   The `user_id` filter is inside the query, never applied afterwards.

5. **`services/knowledge/ingest.py`** — orchestrates
   `extract → clean → chunk → embed → store`, updating `KnowledgeDocument.status` at every stage
   so the UI can show `Extracting → Chunking → Embedding → Indexed` (plan §21). On failure: status
   `failed`, `error_message` set to a *user-safe* string, exception logged server-side.

6. **`api/endpoints/knowledge.py`** (plan §28)
   | Method | Path | Behaviour |
   |---|---|---|
   | GET | `/api/knowledge` | User's documents + chunk counts |
   | POST | `/api/knowledge/upload` | Multipart; validate; store; status `uploaded` |
   | POST | `/api/knowledge/{id}/process` | Run ingestion (ownership-checked) |
   | DELETE | `/api/knowledge/{id}` | Cascade-delete chunks (ownership-checked) |
   | POST | `/api/knowledge/search` | Manual search — also the debug surface for the demo |

   Upload may process inline (simplest, ~2–5 s for demo documents) or return immediately and
   process on the `/process` call. **Inline-on-upload plus a manual re-process button is the
   lower-risk choice** — it avoids background-task lifecycle problems on serverless.

7. **Register the router** in `main.py` under `/api/knowledge`.

### Acceptance
- [ ] Upload a `.md` file → status reaches `indexed`, `chunk_count > 0`
- [ ] `SELECT embedding FROM knowledge_chunks LIMIT 1` returns a real 1536-dim vector
- [ ] `POST /api/knowledge/search {"query": "inventory management"}` returns ranked chunks with
      similarity scores that are actually ordered
- [ ] **User B searching User A's exact query returns zero results** — the isolation proof
- [ ] A 12 MB file is rejected with 400; a `.exe` is rejected with 400
- [ ] Deleting a document removes its chunks

### Risks
- **Embedding-dimension mismatch** is the most likely failure. Assert loudly and early.
- Provider rate limits on batch embedding — batch modestly and handle 429 with one retry.
- ivfflat needs data before it helps; with <1000 chunks a sequential scan is fine and correct.

### Summary → `docs/summery/phase-3-rag-pipeline.md`

---

# Phase 4 — Autonomous sales agent & tools

**Goal:** one agent that *decides* to retrieve knowledge, reason, plan, and act via tools.
**Budget:** 2.5 h · **Depends on:** 2, 3 · **Risk: HIGH — largest refactor in the project**

### Current state
`agent_core/orchestrator.py` builds `model_heavy` / `model_medium` / `model_openrouter` at module
import from global env vars, and defines three sub-agents as tools. Tracing works. There is no
single autonomous sales agent and no per-user model resolution.

### Tasks

1. **`agent_core/model_factory.py`** — break the global-singleton pattern (rule §3.4)
   ```python
   def build_model(cfg: ResolvedLLMConfig) -> OpenAIChatCompletionsModel
   ```
   Same `AsyncOpenAI(api_key, base_url)` + `OpenAIChatCompletionsModel(model)` shape as
   `orchestrator.py:_make_model` — but called **per run**, with the authenticated user's config.
   Leave the chat orchestrator's module-level models alone for now (Decision D1); note the
   remaining debt in the phase summary.

2. **`agent_core/sales_tools.py`** — the four tools that matter (plan §13)

   | Tool | Signature | Notes |
   |---|---|---|
   | `search_knowledge` | `(query: str, top_k: int = 5)` | **plan §11 — the critical one.** Calls Phase 3 search with `wrapper.context.user_id`. The agent decides *when* to call it; RAG is never pre-fetched before the LLM. |
   | `get_lead` | `(lead_id: str)` | User-scoped read. |
   | `update_lead` | `(lead_id, status?, score?, pain_points?, notes?)` | User-scoped write. Rejects a lead owned by another user. |
   | `draft_outreach` | `(lead_id, subject, body)` | Persists an `OutreachDraft` with status `draft`. **Never sends.** Human approval is a separate endpoint (plan §13 Tool 6). |

   Optional, only if stable and time remains: `create_erpnext_opportunity` wrapping the existing
   `mcp_tools/erpnext.py` — must degrade gracefully when ERPNext is unconfigured.

3. **`agent_core/sales_agent.py`** — the single autonomous agent (plan §12, §34)
   - `SalesAgentContext(run_id, user_id, lead_id, llm_cfg, embed_cfg)` — threaded to every tool
     through `RunContextWrapper`, exactly as `AgentContext` already is.
   - System prompt encoding the loop: **OBSERVE → RETRIEVE → REASON → PLAN → ACT → RESULT**, with
     an explicit instruction to call `search_knowledge` before qualifying any lead.
   - Structured final output (plan §14):
     ```json
     { "lead_score": 93, "qualification": "Qualified", "reasoning": "...",
       "pain_points": [], "matched_knowledge": [], "recommended_action": "...",
       "outreach": { "subject": "...", "body": "..." } }
     ```
     Use the SDK's `output_type` with a Pydantic model so parsing is not string-scraping.
   - **Do not expose hidden chain-of-thought** (plan §14). `reasoning` is a concise business
     rationale, not internal deliberation.

4. **`agent_core/events.py`** — semantic phase events (plan §6, §20; see REUSE_MAP §7)
   ```python
   async def emit(run_id, user_id, phase, title, detail=None, payload=None)
   ```
   Writes `AgentEvent` rows with a monotonic `sequence`. Called at each phase boundary **in
   addition to** the automatic span tracing — span types cannot be mapped back to business phases.
   Reuse `tracing.py`'s pending-write + `flush_pending_writes()` discipline; on serverless,
   fire-and-forget tasks are cancelled when the response returns.

5. **`run_sales_agent(lead_id, user_id, db)`**
   - Resolve the user's LLM + embedding config → build model → build agent → `Runner.run_streamed`.
   - Create the `WorkflowRun` (`workflow_type="lead_analysis"`, `lead_id`, `status="running"`).
   - Emit `OBSERVE` on start, `TOOL_CALL`/`RESULT` per tool from the stream, `COMPLETE` at the end.
   - On success: persist `final_result`, `completed_at`, `status="completed"`.
   - On failure: `status="failed"`, emit an `ERROR` event with a user-safe message, **flush
     pending writes**, log the real cause server-side.

6. **Secret hygiene** (plan §56) — traces record
   `LLM Provider: <name> · Model: <model> · Status: success`. Never an API key, never a token.
   Audit every `logger` call and every event payload added in this phase.

### Acceptance
- [ ] Running as User A uses User A's LLM config; as User B, User B's — verified by pointing them
      at different models and reading `audit_traces.model_name`
- [ ] The agent calls `search_knowledge` **on its own**, without being told to in the user message
- [ ] `tool_call_logs` shows real `search_knowledge`, `update_lead`, `draft_outreach` invocations
- [ ] The lead row's `status` and `score` actually change after a run
- [ ] `agent_events` contains an ordered OBSERVE → … → COMPLETE sequence
- [ ] The final result parses into the plan §14 structure
- [ ] A user with no LLM configuration gets a 400 with an actionable message, not a 500
- [ ] `grep -iE "sk-|api[_-]?key|bearer" ` over captured logs and `agent_events` finds nothing

### Risks
- **Weaker models skip tool calls** and answer from priors. Mitigate with an explicit prompt
  instruction plus a re-prompt if `search_knowledge` was never called. Verify with the actual
  configured demo model early in the phase — not at the end.
- Structured output support varies across OpenAI-compatible providers. Have a JSON-parse fallback
  ready if `output_type` is unsupported by the demo provider.
- The per-run agent build costs a few ms — irrelevant, and it is what correctness requires.

### Summary → `docs/summery/phase-4-sales-agent.md`

---

# Phase 5 — Leads, analyze & run/trace APIs

**Goal:** every endpoint the dashboard needs, all user-scoped.
**Budget:** 1.5 h · **Depends on:** 4

### Current state
`GET /api/dashboard/leads` reads ERPNext (global, not user-scoped). `/api/runs` and
`/api/workflows/{id}/logs` exist and already enforce ownership — good foundations.

### Tasks

1. **`api/endpoints/leads.py`** (plan §18, §28)
   | Method | Path | Behaviour |
   |---|---|---|
   | GET | `/api/leads` | List; `?search=&status=&limit=&offset=`; user-scoped |
   | POST | `/api/leads` | Create |
   | GET | `/api/leads/{id}` | Detail + agent runs + outreach drafts (404 if not owner) |
   | PATCH | `/api/leads/{id}` | Update |
   | DELETE | `/api/leads/{id}` | Delete |
   | POST | `/api/leads/{id}/analyze` | **The core CTA.** Verify ownership → `run_sales_agent` → return `{run_id, status, result}` |

2. **Extend `api/endpoints/runs.py`**
   - `GET /api/runs` — add `lead_id`, `lead_company`, `score`, `qualification`, `completed_at`.
   - `GET /api/runs/{id}` — add the parsed `final_result`.
   - **New `GET /api/runs/{id}/events`** — ordered `AgentEvent` rows. This is what the live
     timeline polls (Decision D6). Support `?after_sequence=N` so polling is incremental.

3. **Adapt `api/endpoints/dashboard.py`** (plan §17)
   Re-point `GET /api/dashboard/stats` at local user-scoped data:
   `total_leads · qualified_leads · outreach_sent · active_agent_runs · knowledge_documents`,
   plus recent leads, recent runs, and recent actions. Keep the ERPNext pipeline block only as an
   optional extra that never blocks the response when ERPNext is unconfigured.

4. **`POST /api/outreach/{draft_id}/approve`** — mark approved and send via the user's email
   config (plan §20). Sending is optional; **approval must work even when email is not
   configured** — never let outreach delivery block the demo (plan §13).

### Acceptance
- [ ] Full lead CRUD works and is user-scoped
- [ ] `POST /api/leads/{id}/analyze` returns a `run_id` and the lead is genuinely updated
- [ ] `GET /api/runs/{id}/events` returns the ordered phase timeline
- [ ] User A requesting User B's lead / run / draft id gets **404**, never data
- [ ] `GET /api/dashboard/stats` returns non-zero counts after seeding
- [ ] Dashboard stats still respond when ERPNext is unreachable

### Summary → `docs/summery/phase-5-leads-runs-api.md`

---

# Phase 6 — Demo seed data

**Goal:** the dashboard never opens empty, and RAG has something real to retrieve.
**Budget:** 0.5 h · **Depends on:** 3, 5

### Tasks

1. **`scripts/seed_demo.py`** — idempotent (safe to re-run), takes `--user-email`.
2. **Two users** (plan §58): create User A and User B in Neon Auth, seed distinct data for each.
   This is what makes the Phase 10 isolation test meaningful.
3. **~5 leads for User A** (plan §25), with varied scores and statuses so the dashboard looks
   real: Acme Manufacturing (Manufacturing, inventory visibility, New) · PakTech Industries
   (Industrial, manual sales operations, New) · Karachi Components Ltd (Manufacturing, supply
   chain inefficiency, New) · plus two already-qualified leads with scores.
   **Leave Acme Manufacturing at `New`** — it is the live demo subject and must be analyzed on
   stage, not pre-analyzed.
4. **2–3 distinct leads for User B** — different companies, so cross-user leakage is visible at a
   glance if it ever occurs.
5. **4 knowledge documents for User A** (plan §26) as `.md` files under `scripts/demo_knowledge/`:
   Manufacturing Solutions · Inventory Management Case Study · Company Products · Sales Playbook.
   Content must genuinely cover inventory management, ERP integration, manufacturing workflows,
   sales automation, business benefits, and customer case studies — the agent has to *retrieve*
   this, so thin filler content produces a thin demo.
6. **Run the real ingestion pipeline** on those documents. Do not fake embeddings.
7. **1–2 knowledge documents for User B**, on a clearly different topic.

### Acceptance
- [ ] Re-running the script does not duplicate rows
- [ ] User A: 5 leads, 4 indexed documents, chunks with real embeddings
- [ ] User B: separate leads and documents
- [ ] `POST /api/knowledge/search {"query":"inventory management manufacturing"}` as User A
      returns Manufacturing Solutions and the Inventory case study
- [ ] The same query as User B returns User B's content only

### Summary → `docs/summery/phase-6-seed-data.md`

---

# Phase 7 — Next.js scaffold, auth & app shell

**Goal:** a running, authenticated, navigable web app.
**Budget:** 1.5 h · **Depends on:** 5

### Current state
`querysales-web/` does not exist. `salesopsapp/` supplies the design language and the known-good
auth flow.

### Tasks

1. **Scaffold** — `npx create-next-app@latest querysales-web --typescript --tailwind --app --eslint`
   at the repo root. No `src/` directory (plan §15; keep it consistent with the rules files).

2. **Design tokens** — port `salesopsapp/src/theme.ts` into Tailwind CSS variables in
   `app/globals.css`: background `#07111F`, surface `#0D1728`, primary `#6D5CFF`, secondary
   `#885CF6`, accent `#36CFFF`, success `#2BE4B8`. Define the complete light palette on `:root`,
   redefine only what changes under dark. Clean modern SaaS — no bespoke design system (plan §15).

3. **Auth** (plan §16, Decision D4) — mirror `salesopsapp/src/services/authService.ts`:
   - `app/login/page.tsx` — email + password, loading/error states.
   - `app/api/auth/login/route.ts` — `POST {NEON_AUTH_URL}/sign-in/email` →
     `GET {NEON_AUTH_URL}/token` → set the JWT as an **httpOnly, secure, sameSite=lax cookie**.
   - `app/api/auth/logout/route.ts` — clear the cookie.
   - `middleware.ts` — redirect unauthenticated requests to `/login`; redirect authenticated
     requests away from `/login` to `/dashboard`.

4. **`lib/api-client.ts`** — **server-only** (`import 'server-only'`). Reads the cookie, attaches
   `Authorization: Bearer <jwt>`, calls `process.env.API_URL`. One place that maps a 401 to a
   logout redirect and everything else to a typed error. `API_URL` is **not** `NEXT_PUBLIC_*`.

5. **`lib/types.ts`** — TypeScript types mirroring the backend Pydantic models.

6. **App shell** (plan §23) — `app/(dashboard)/layout.tsx` with the sidebar:
   `QuerySales AI · Dashboard · Leads · Knowledge · Agent Runs · Settings · — · User · Logout`.
   Active-route highlighting; collapses on mobile.

7. **Shared UI primitives** in `components/ui/` — only what is actually used: `card`, `badge`,
   `button`, `table`, `input`, `skeleton`, `empty-state`, `error-state`. Status badges get a
   colour per lead status.

8. **`.env.example`** — `API_URL`, `NEON_AUTH_URL`, `NEXT_PUBLIC_APP_URL`.

### Acceptance
- [ ] `npm run dev` serves `/login`
- [ ] Logging in with a seeded user redirects to `/dashboard`
- [ ] The JWT is in an httpOnly cookie and is **not** readable from `document.cookie`
- [ ] Visiting `/dashboard` while logged out redirects to `/login`
- [ ] Logout clears the session
- [ ] `npm run build` passes with zero errors
- [ ] The sidebar renders and navigates on desktop and mobile

### Risks
Neon Auth may return the session token in a `set-cookie` header rather than the body — the RN
`extractToken` helper handles both; port that logic, including the `=`-rejoin that preserves
base64 padding.

### Summary → `docs/summery/phase-7-nextjs-shell.md`

---

# Phase 8 — Dashboard, leads & live analysis UI

**Goal:** the screens the demo is judged on.
**Budget:** 2.0 h · **Depends on:** 6, 7 · **Risk: HIGH — the money screens**

### Tasks

1. **`/dashboard`** (plan §17) — server component fetching `/api/dashboard/stats`
   - **KPI cards:** Total Leads · Qualified Leads · Outreach Sent · Active Agent Runs ·
     Knowledge Documents.
   - **Lead overview table:** Company · Industry · Lead Score · Status · Last Activity.
   - **Agent activity:** recent runs — `Acme Manufacturing · Qualified — 93 · 2 minutes ago`.
   - **Recent actions:** Knowledge Retrieved · Lead Updated · Email Drafted · Opportunity Created.
   - Skeletons while loading; an empty state that points at seeding.

2. **`/leads`** (plan §18) — list with search, status filter, score and status columns. Search and
   filter are client-side state driving a server refetch through `searchParams`.

3. **`/leads/[id]`** (plan §18) — Company · Contact · Industry · Website · Pain Points · Score ·
   Status · Notes · Agent Actions. Primary CTA: **Analyze with QuerySales AI**.
   `params` is a `Promise` in Next 16 — `await` it.

4. **The live analysis experience** (plan §19) — *the most important screen in the demo*
   - Clicking the CTA `POST`s to `/api/leads/{id}/analyze` and immediately shows a timeline.
   - A client component polls `GET /api/runs/{run_id}/events?after_sequence=N` every ~1 s and
     appends phases as they arrive (Decision D6 — SSE is not available).
   - Each phase animates in with a check and a label:
     `✓ Lead loaded · ✓ Understanding lead requirements · ✓ Searching company knowledge ·
     ✓ Retrieved 4 relevant documents · ✓ Evaluating product fit · ✓ Creating sales action plan ·
     ✓ Updating lead · ✓ Drafting personalized outreach · ✓ Analysis complete`
   - On completion: show score, qualification, reasoning, matched knowledge, and the outreach
     draft, then link to `/runs/[id]`.
   - **Failure is a first-class state** — a failed run renders the error phase and a retry button,
     never an infinite spinner.

5. **Shared components** — `components/leads/`, `components/dashboard/`,
   `components/agent/analysis-timeline-client.tsx`.

### Acceptance
- [ ] The dashboard shows real seeded numbers, not placeholders
- [ ] Lead search and status filter work
- [ ] Clicking **Analyze with QuerySales AI** on Acme Manufacturing streams a visible,
      progressive timeline
- [ ] The timeline shows the real `search_knowledge` call and the documents actually retrieved
- [ ] The lead's status and score visibly change when the run completes
- [ ] Polling stops on completion or failure — no runaway request loop
- [ ] Loading, error, and empty states exist on every panel
- [ ] Responsive at 375 px and 1440 px
- [ ] `npm run build` passes · no console errors

### Risks
- **A long agent run makes the CTA feel dead.** Emit `OBSERVE` before the first LLM call so the
  first phase appears within a second.
- Polling must clear its interval on unmount, on completion, and on failure.

### Summary → `docs/summery/phase-8-dashboard-leads-ui.md`

---

# Phase 9 — Knowledge, run detail & settings UI

**Goal:** the supporting screens that prove the system is real.
**Budget:** 1.5 h · **Depends on:** 7, 8

### Tasks

1. **`/knowledge`** (plan §21)
   - Table: Document · Type · Chunks · Status · Created · Actions.
   - **Upload Knowledge** button — client-side type/size validation before the request, mirroring
     the server rules.
   - Live status progression: `Extracting → Chunking → Embedding → Indexed`.
   - Delete with confirmation. Empty state invites the first upload.

2. **`/runs`** — list of the user's agent runs: lead, qualification, score, duration, status.

3. **`/runs/[id]`** (plan §20)
   - Header: `Agent Run · Acme Manufacturing · Qualified · 93/100`.
   - **Expandable timeline** — Observe → Retrieve → Tool Call → Reason → Plan → Action → Result.
     - `SEARCH_KNOWLEDGE` expands to the query, result count, and source documents.
     - `TOOL CALL` expands to tool name and arguments (`update_lead · Status: Qualified · Score: 93`).
     - `OUTREACH DRAFT` expands to subject and body with an **Approve & Send** action.
   - Long values scroll inside their own container — the page body never scrolls horizontally.

4. **`/settings`** (plan §22, §53)
   - Sections: **AI / LLM · Embeddings · Email / Outreach · Database**.
   - Status chips: `LLM ✓ Configured · Embeddings ✓ Configured · Email ✓ Connected`.
   - API-key inputs show `••••••••` with **Update API Key** / **Remove Configuration** — the
     stored secret is never fetched into the browser (plan §47).
   - **Test Connection** per section, showing only success/failure.
   - Database section shows PostgreSQL `Connected` and pgvector `Enabled` — never the DSN.

### Acceptance
- [ ] Uploading a `.md` file indexes it and the chunk count appears
- [ ] An oversized or wrong-type file is rejected client-side *and* server-side
- [ ] The run detail timeline expands to show the real knowledge query and its sources
- [ ] **Approve & Send** creates/sends the outreach and reflects the new status
- [ ] Settings save, then re-open showing `configured: true` and a masked key
- [ ] **Test Connection** succeeds against a real provider and fails cleanly against a bad key
- [ ] No API key is present in any network response — check DevTools
- [ ] `npm run build` passes

### Summary → `docs/summery/phase-9-knowledge-runs-settings-ui.md`

---

# Phase 10 — Isolation verification, E2E demo & polish

**Goal:** prove the acceptance criteria hold, then make it demo-ready.
**Budget:** 1.0 h · **Depends on:** all

### Tasks

1. **Multi-user isolation test** (plan §58) — with User A and User B logged in side by side:
   - A sees only A's leads, knowledge, runs, settings; likewise B.
   - Requesting B's lead/run/document/draft id as A returns **404**.
   - `POST /api/knowledge/search` as B never returns A's chunks.
   - A's LLM/embedding/email keys are unreachable through any request as B.
   - Record the exact requests and responses in the phase summary — this is a stated acceptance
     criterion, not an informal check.

2. **Secret-leak sweep** (plan §56) — grep captured server logs, agent traces, `agent_events`
   payloads, and browser network responses for `sk-`, `api_key`, `Bearer `, `password`,
   `refresh_token`. Expected result: zero hits.

3. **Full E2E demo rehearsal** (plan §27) — Login → Dashboard (5 leads, 2 qualified, 4 documents)
   → Acme Manufacturing → **Analyze with QuerySales AI** → timeline → real pgvector retrieval →
   score 93 / Qualified → lead updated by tool → personalized outreach → Approve & Send →
   dashboard counters increment. **Run it end to end at least twice.**

4. **Final quality check** (plan §38) — walk the backend, frontend, and demo checklists literally
   and record actual results, including failures.

5. **Polish, strictly time-boxed** — loading skeletons, error copy, empty states, responsive
   check at 375/768/1440, remove console noise, tidy `README.md` with real setup steps.

6. **Update `AGENTS.md`** — mark all phases complete in §9, record final decisions in §8, add
   remaining known gaps to §7.

### Acceptance — the Definition of Done in [AGENTS.md §10](../AGENTS.md#10-definition-of-done)

### Summary → `docs/summery/phase-10-verification-demo.md`

---

## Deferred — P1 (only if time remains)

PDF extraction quality · true event streaming · Gmail draft API (as opposed to SMTP send) ·
charts on the dashboard · advanced lead filters · full-text search alongside pgvector (hybrid
retrieval, plan §33) · refactoring the chat orchestrator onto per-user configs (the remaining
half of rule §3.4) · animation polish.

## Not building — P2 (plan §3, §32)

WhatsApp · voice/calling · LinkedIn automation · multi-agent swarm · advanced scraping · billing ·
teams · enterprise RBAC · the mobile application · complex analytics · deployment automation ·
Kubernetes · event-driven infrastructure.
