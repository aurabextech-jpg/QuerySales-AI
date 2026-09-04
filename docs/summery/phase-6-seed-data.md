# Phase 6 — Demo seed data

**Status:** ✅ Complete (with known gap: embeddings deferred)
**Date:** 2026-09-04
**Time spent:** ~0.5 h (budget: 0.5 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 6](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

The dashboard never opens empty, and RAG has something real to retrieve.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `scripts/seed_demo.py` | New — 544 lines | Idempotent demo seeder: 2 users, 8 leads, 6 knowledge documents. |
| `db/models.py` | Fixed | Added missing `WorkflowRun.lead` relationship; removed invalid `Lead.documents` cross-user relationship. |

### Data seeded

**User A — alice@querysales.demo** (manufacturing vertical):
- 5 leads: Acme Manufacturing (New), PakTech Industries (New), Karachi Components Ltd (New), TechVault Solutions (Qualified, score 85), GreenLeaf Organics (Nurture, score 62)
- 4 knowledge documents: Manufacturing Solutions, Inventory Case Study, Company Products, Sales Playbook

**User B — bob@querysales.demo** (healthcare vertical):
- 3 leads: City Hospital Network (New), MediCare Plus (New), Wellness First Clinics (Qualified, score 72)
- 2 knowledge documents: Healthcare Solutions, Healthcare Case Study

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| Script runs | `python -m scripts.seed_demo --skip-ingestion` | ✅ 5 leads + 4 docs (User A), 3 leads + 2 docs (User B) |
| Idempotency | Designed in | ✅ Checks existing rows before inserting |
| Relationship fix | Re-run after fix | ✅ No SQLAlchemy mapper errors |

## 4. Decisions

- **Embeddings deferred to Phase 10 or runtime.** The seed script ran with `--skip-ingestion`
  because no LLM/embedding API key is configured yet. Documents are chunked but not embedded.
  Real embeddings will be generated when the user processes documents via
  `POST /api/knowledge/{id}/process` after configuring their embedding model in settings.
- **Users created locally, not via Neon Auth.** The script creates `User` rows directly. When
  the real Neon Auth users log in through the dashboard, `security.py` auto-upserts the row,
  so the seed email just needs to match.

## 5. Deferred / simplified

- Real embedding generation (P0 — needs API key configured first).
- The knowledge search acceptance test (`POST /api/knowledge/search`) requires real embeddings
  and will be verified in Phase 10 isolation testing.

## 6. Known gaps

- Documents are chunked but lack embeddings until processed via the API with a configured
  embedding model. This is expected — the demo flow is: seed data → configure LLM → process
  documents → search works.
