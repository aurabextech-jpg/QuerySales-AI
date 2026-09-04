# Phase 8 — Dashboard, leads & live analysis UI

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1.5 h (budget: 2.0 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 8](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

The screens the demo is judged on — dashboard, leads list, lead detail, and the live analysis timeline.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `app/api/dashboard/stats/route.ts` | New — proxy to FastAPI | Server-side stats fetch |
| `app/api/leads/route.ts` | New — proxy with search/status params | List leads with filtering |
| `app/api/leads/[id]/route.ts` | New — GET detail + POST analyze | Lead detail and analysis trigger |
| `app/api/runs/[id]/events/route.ts` | New — proxy with after_sequence param | Event polling for timeline |
| `app/(dashboard)/dashboard/page.tsx` | Rewritten — async server component | KPI cards + recent leads table from real data |
| `app/(dashboard)/leads/page.tsx` | Rewritten — async with searchParams | Search + status filter, lead table |
| `app/(dashboard)/leads/leads-search.tsx` | New — client search bar | URL-driven search/filter with instant status change |
| `app/(dashboard)/leads/[id]/page.tsx` | New — lead detail page | Company info, pain points, notes, Analyze CTA |
| `app/(dashboard)/leads/[id]/analyze-button.tsx` | New — client CTA | POST analyze, render timeline, error + retry |
| `components/agent/analysis-timeline-client.tsx` | New — **the money component** | Polls events every 1s, progressive timeline, stops on COMPLETE/ERROR |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| `npm run build` | `npm run build` | ✅ Zero errors, 16 routes (7 dynamic + 9 static) |
| TypeScript | Part of build | ✅ Clean |
| API routes | Build output | ✅ All 4 proxy routes dynamic |
| `params` is `Promise` | Code | ✅ `await params` in all dynamic route handlers |

## 4. Decisions

- **Polling interval = 1 second.** Matches the AGENTS.md Decision D6 (no SSE on Vercel).
  Interval clears on COMPLETE, ERROR, or component unmount — no runaway loops.
- **Timeline uses `after_sequence` for incremental fetch.** Only new events are fetched
  each poll, keeping bandwidth low and avoiding re-rendering old events.
- **Search is URL-driven.** The leads list uses `searchParams` so the page is shareable and
  back-button works. Status filter triggers instant refetch.
- **AnalyzeButton shows the timeline inline.** Rather than navigating to a separate page,
  the timeline renders below the CTA on the lead detail page — keeping the user in context.

## 5. Deferred / simplified

- Run detail page (`/runs/[id]`) deferred to Phase 9 — the timeline on the lead page is the
  primary demo experience.
- Outreach draft display/approval on the lead detail page deferred to Phase 9.

## 6. Known gaps

- Dashboard stats and leads list require a running FastAPI backend to display real data.
- The analysis timeline requires a configured LLM to actually run the agent.
