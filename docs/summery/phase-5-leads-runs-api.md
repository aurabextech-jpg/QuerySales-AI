# Phase 5 — Leads, analyze & run/trace APIs

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1 h (budget: 1.5 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 5](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

Every endpoint the dashboard needs, all user-scoped.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `api/endpoints/leads.py` | New — 7 endpoints | GET list (search/filter), POST create, GET/PATCH/DELETE detail, POST analyze, POST outreach approve. |
| `api/endpoints/runs.py` | Extended | Added `lead_id`, `lead_company`, `score`, `qualification`, `completed_at` to summaries. New `GET /{id}/events` for timeline polling. |
| `api/endpoints/dashboard.py` | Adapted | `_fetch_local_pipeline()` reads local leads table. ERPNext is optional extra. Added `knowledge_documents` and `outreach_drafts` counts. |
| `main.py` | Registered leads router | `/api/leads` prefix. |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| Leads routes | `_verify_p5.py` | `[OK] 8 leads routes` |
| Runs routes | `_verify_p5.py` | `[OK] 4 runs routes` |
| Events endpoint | path check | `[OK] /api/runs/{id}/events` |
| Outreach approve | path check | `[OK] /api/leads/outreach/{id}/approve` |
| Dashboard adapted | `_verify_p5.py` | `[OK] 3 dashboard routes` |
| Pydantic models | import + instantiation | `[OK]` |
| Total routes | `main.app.routes` | `[OK] 49 total` |

## 4. Decisions

- **Outreach approval never blocks on email.** `approve_outreach` always marks
  the draft as "approved" even when email is not configured. SMTP send is
  best-effort. This matches plan §13: "never let outreach delivery block the demo."
- **Dashboard stats read local leads first.** ERPNext pipeline data is tried
  as an optional extra but never blocks the response when ERPNext is unconfigured.

## 5. Deferred / simplified

- Dashboard `/leads` endpoint (ERPNext-backed) still exists as legacy — the
  new local leads CRUD is in `api/endpoints/leads.py`. The frontend will use
  the new endpoint.

## 6. Known gaps

None blocking.
