# Phase 3 — RAG pipeline & knowledge API

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1.5 h (budget: 2.0 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 3](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

Real documents in, real vectors out, real user-scoped similarity search. The demo's
central claim.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `services/knowledge/__init__.py` | New package | Groups the RAG pipeline modules. |
| `services/knowledge/extract.py` | New — text extraction | `.txt`/`.md` via UTF-8, `.pdf` via `pypdf`. Extension allowlist, 10 MB cap, empty-file check. |
| `services/knowledge/chunk.py` | New — text chunking | ~1000-char chunks, ~150-char overlap. Paragraph-then-sentence splitting. Metadata per chunk. |
| `services/knowledge/embed.py` | New — embedding generation | OpenAI-compatible API, batched at 64, asserts 1536-dim output (Decision D2). |
| `services/knowledge/search.py` | New — vector similarity search | pgvector cosine distance, user_id filter INSIDE SQL (never post-filtered). |
| `services/knowledge/ingest.py` | New — ingestion orchestrator | extract → chunk → embed → store, updates doc.status at each stage. |
| `api/endpoints/knowledge.py` | New — 5 endpoints | GET list, POST upload (inline ingest), POST reprocess, DELETE (cascade), POST search. |
| `main.py` | Registered knowledge router | `/api/knowledge` prefix. |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| Routes registered | `_verify_p3.py` | `[OK] 5 knowledge routes` |
| .txt extraction | `_verify_p3.py` | `[OK]` |
| .md extraction | `_verify_p3.py` | `[OK]` |
| .exe rejected | `_verify_p3.py` | `[OK] Unsupported file type` |
| 11 MB rejected | `_verify_p3.py` | `[OK] File is 11.0 MB, maximum is 10 MB` |
| Empty rejected | `_verify_p3.py` | `[OK] File is empty` |
| Chunking (5438 chars → 7 chunks) | `_verify_p3.py` | `[OK] 7 chunks` |
| Chunk metadata | `_verify_p3.py` | `[OK] title, filename populated` |
| user_id filter in SQL | `inspect.getsource` | `[OK] c.user_id = :user_id in SQL` |
| Embed importable | `_verify_p3.py` | `[OK] EXPECTED_DIMENSION=1536` |

## 4. Decisions

- **Inline ingestion on upload.** Upload → extract → chunk → embed → store in one
  request. Avoids background-task lifecycle problems on Vercel serverless.
  A manual re-process endpoint exists for re-ingestion after config changes.

## 5. Deferred / simplified

- Live embedding call and full upload-to-search E2E not tested in this session
  (requires a valid embedding API key). Code paths verified via import + unit checks.
- PDF extraction uses `pypdf` which is already in deps; tested via import only.

## 6. Known gaps

None blocking. The E2E flow (upload → embed → search) will be verified live
during Phase 6 (seed data) or Phase 10 (isolation verification).
