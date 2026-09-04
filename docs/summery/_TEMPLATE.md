# Phase <N> — <Phase Name>

**Status:** ✅ Complete | ⚠️ Complete with known gaps
**Date:** YYYY-MM-DD
**Time spent:** <actual> (budget: <planned>)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase <N>](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

One or two sentences: what this phase was supposed to achieve.

## 2. What was built

Files created or modified, with one line each on **why**.

| File | Change | Why |
|---|---|---|
| `path/to/file.py` | Created | … |
| `path/to/other.py` | Modified | … |

## 3. What was verified — and how

Every claim needs the command that backs it and its **actual** result. "Should work" is not
verification. If something failed, record the failure and what was done about it.

| Check | Command / action | Result |
|---|---|---|
| … | `…` | ✅ / ❌ + actual output |

Acceptance criteria from the plan:

- [ ] …
- [ ] …

## 4. Decisions made

| Decision | Alternatives considered | Why this one |
|---|---|---|
| … | … | … |

Add any architectural decision to [AGENTS.md §8 Decision Log](../../AGENTS.md#8-decision-log).

## 5. Deferred or simplified

What was scoped down, and to where (P1 / P2 / a later phase). Include *why* — a future session
needs to know whether this was a time trade-off or a technical constraint.

| Item | Deferred to | Reason |
|---|---|---|
| … | P1 | … |

## 6. Discovered — affects later phases

Anything learned that changes a downstream phase's assumptions, estimate, or approach. This is
the highest-value section of the summary. If a later phase's plan is now wrong, say so explicitly.

## 7. Known gaps & follow-ups

Open issues left behind, with enough detail to act on without re-deriving the context.

## 8. Memory updates applied

Confirm the durable context was written back:

- [ ] [AGENTS.md §7 Project Memory](../../AGENTS.md#7-project-memory) — new non-obvious facts
- [ ] [AGENTS.md §8 Decision Log](../../AGENTS.md#8-decision-log) — new decisions
- [ ] [AGENTS.md §9 Phase Status](../../AGENTS.md#9-phase-status) — this phase's row updated

## 9. Next phase

Phase <N+1> — <name>. Anything the next phase should know before it starts.
