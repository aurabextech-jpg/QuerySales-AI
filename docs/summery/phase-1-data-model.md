# Phase 1 — Data model & migrations

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~0.75 h (budget: 1.0 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 1](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

Create every new table the product needs: leads, knowledge documents + chunks (pgvector),
per-user config (LLM / embedding / email), agent events, outreach drafts. Extend
`workflow_runs` with `lead_id`, `final_result`, `completed_at`.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `db/models.py` | Rewrote with 14 ORM models | Added `Lead`, `KnowledgeDocument`, `KnowledgeChunk` (vector(1536)), `UserLLMConfig`, `UserEmbeddingConfig`, `UserEmailConfig`, `AgentEvent`, `OutreachDraft`. Extended `WorkflowRun`. Kept all legacy tables unchanged. |
| `alembic/versions/6c7f6e87625b_querysales_core_schema.py` | New migration (after `b7c8d9e0f1a2`) | Creates 8 new tables, adds columns to 3 existing tables, enables pgvector extension, creates IVFFlat index. |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| All 8 new tables exist | `_verify_p1.py` → `pg_tables` query | `[OK] Phase 1 tables: all present` |
| pgvector enabled | `pg_extension` query | `[OK] pgvector version: 0.8.6` |
| Embedding column is vector type | `information_schema.columns` | `[OK] embedding column type: ('vector', None)` |
| IVFFlat index | `pg_indexes` query | `[OK] vector index: ['knowledge_chunks_embedding_idx']` |
| Composite indexes | `pg_indexes` query | `[OK] ix_leads_user_status`, `[OK] ix_agent_events_run_seq` |
| workflow_runs new cols | `information_schema.columns` | `[OK] workflow_runs new cols: all present` |
| All tables have user_id | column check per table | `[OK] All Phase 1 tables have user_id` |
| Downgrade/upgrade round-trip | `alembic downgrade -1 && alembic upgrade head` | Both EXIT 0 |
| Models importable | `python -c "from db.models import *"` | No errors |

## 4. Decisions

- **FK constraint naming**: Postgres auto-names FKs as `{table}_{col}_fkey` regardless of the
  name passed to `op.create_foreign_key`. Downgrade uses the actual auto-generated name
  (`workflow_runs_lead_id_fkey`), not the name we passed.
- **IVFFlat lists = 100**: Default for demo-scale data. Production would tune based on row count.

## 5. Deferred / simplified

Nothing deferred.

## 6. Known gaps

- `workflow_steps` table still exists but is unused (by design — AGENTS.md §7).
- The `Lead.documents` relationship uses a manual `foreign_keys` arg to avoid ambiguity;
  not a gap, just non-obvious.
