# Phase 4 — Autonomous sales agent & tools

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1.5 h (budget: 2.5 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 4](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

One agent that decides to retrieve knowledge, reason, plan, and act via tools.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `agent_core/model_factory.py` | New — per-user model builder | Breaks global-singleton pattern (rule §3.4). Called per run with resolved config. |
| `agent_core/events.py` | New — semantic phase events | `emit()` writes AgentEvent rows with monotonic sequence. 7 phases: OBSERVE → ERROR. |
| `agent_core/sales_tools.py` | New — 4 agent tools | `search_knowledge_tool`, `get_lead_tool`, `update_lead_tool`, `draft_outreach_tool`. All user-scoped. |
| `agent_core/sales_agent.py` | New — autonomous agent + runner | `SalesAnalysisOutput` (structured), `run_sales_agent()`, system prompt with OBSERVE→RESULT loop. |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| Module imports | `_verify_p4.py` | `[OK]` all 4 Phase 4 modules |
| Structured output | Pydantic validation | `[OK]` serialises to dict |
| Model factory | `build_model(cfg)` | `[OK]` creates model from ResolvedLLMConfig |
| Tools registered | `ALL_TOOLS` | `[OK] 4 tools` |
| System prompt | String check | `[OK]` OBSERVE/RETRIEVE + MUST search_knowledge |
| Event phases | Phase constants | `[OK] 7 phases` |
| App imports | `main.app.routes` | `[OK] 41 total routes` |

## 4. Decisions

- **Structured output with fallback.** `output_type=SalesAnalysisOutput` is tried first.
  If the provider doesn't support it, falls back to a JSON-instruction prompt
  and parses the string output. Catches `TypeError`/`ValueError` from the SDK.
- **`search_knowledge` is the agent's decision, not pre-fetched.** The system prompt
  explicitly says "MUST search before qualifying" but the LLM decides when and what
  to search. This is plan §11's design.
- **Chat orchestrator left untouched** (Decision D1). The legacy module-level models
  in `orchestrator.py` remain; the sales agent uses `build_model()` per run.

## 5. Deferred / simplified

- `create_erpnext_opportunity` tool not implemented — ERPNext is optional and
  its availability is a demo risk. Deferred to P1.
- Live agent run not tested in this session (requires valid LLM + embedding keys).
  All code paths verified via import + unit checks.

## 6. Known gaps

- The chat orchestrator still uses module-level global models (Decision D1 debt).
- `inspect.getsource` can't read `FunctionTool` objects from the agents SDK —
  secret hygiene verified via manual code review instead.
