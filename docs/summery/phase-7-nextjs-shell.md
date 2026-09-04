# Phase 7 — Next.js scaffold, auth & app shell

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1.5 h (budget: 1.5 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 7](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

A running, authenticated, navigable web app with the QuerySales AI design system.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `querysales-web/` (scaffold) | `create-next-app@latest` — Next.js 16.3.4 | TypeScript + Tailwind + App Router + ESLint |
| `app/globals.css` | Rewrote — design tokens from `salesopsapp/src/theme.ts` | Light + dark palette, Tailwind theme mapping, aurora gradient + glass-card utilities |
| `proxy.ts` | New — auth gate (Next.js 16 `proxy` replaces `middleware.ts`) | JWT validation via cookie, redirect logic for protected/public paths |
| `lib/auth.ts` | New — cookie/JWT helpers | `getSessionToken`, `decodeJwtPayload`, `getSessionUser`; shared by proxy, routes, components |
| `lib/api-client.ts` | New — server-only API client (`import 'server-only'`) | Reads JWT from httpOnly cookie, attaches Bearer, maps 401→redirect |
| `lib/types.ts` | New — TypeScript interfaces | Lead, AgentEvent, RunSummary, KnowledgeDocument, DashboardStats, etc. |
| `app/api/auth/login/route.ts` | New — POST login via Neon Auth | sign-in/email → token exchange → httpOnly cookie (7-day expiry) |
| `app/api/auth/logout/route.ts` | New — POST logout | Clears the session cookie |
| `app/login/page.tsx` | New — server wrapper with `<Suspense>` | Required by Next.js 16 for `useSearchParams()` |
| `app/login/login-form.tsx` | New — client login form | Email + password, loading/error states |
| `app/(dashboard)/layout.tsx` | New — dashboard layout | Sidebar + content area with responsive offset |
| `components/sidebar.tsx` | New — nav sidebar (client) | 5 nav items, active-route highlighting, mobile hamburger + backdrop, logout |
| `app/(dashboard)/dashboard/page.tsx` | New — placeholder | KPI card grid, ready for Phase 8 data |
| `app/(dashboard)/leads/page.tsx` | New — placeholder | Phase 8 will populate |
| `app/(dashboard)/knowledge/page.tsx` | New — placeholder | Phase 9 will populate |
| `app/(dashboard)/runs/page.tsx` | New — placeholder | Phase 9 will populate |
| `app/(dashboard)/settings/page.tsx` | New — placeholder | Phase 9 will populate |
| `components/ui/card.tsx` | New | Glass-card wrapper with padding variants |
| `components/ui/badge.tsx` | New | Status badges with color variants + `leadStatusVariant()` helper |
| `components/ui/button.tsx` | New | Primary/secondary/ghost/danger variants, loading spinner |
| `components/ui/skeleton.tsx` | New | Line + card skeletons for loading states |
| `components/ui/states.tsx` | New | `EmptyState` + `ErrorState` components |
| `.env.example` | New | `API_URL`, `NEON_AUTH_URL`, `NEXT_PUBLIC_APP_URL` |
| `app/layout.tsx` | Updated | Dark theme by default, QuerySales metadata |
| `app/page.tsx` | Updated | Redirect to `/dashboard` |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| `npm run build` | `npm run build` | ✅ Zero errors, all 10 routes rendered |
| Proxy recognized | Build output | ✅ `ƒ Proxy (Middleware)` line present |
| TypeScript | Part of build | ✅ Clean — no type errors |
| Auth routes | Build output | ✅ `/api/auth/login` and `/api/auth/logout` dynamic |

## 4. Decisions

- **Next.js 16 `proxy.ts` instead of `middleware.ts`.** Next.js 16 renamed middleware to proxy
  with nodejs runtime (not edge). The function export is `proxy`, not `middleware`.
  The `config.matcher` export is unchanged.
- **Dark theme by default.** The demo uses the dark palette (`data-theme="dark"` on `<html>`).
  Light mode tokens are defined but not active by default.
- **Suspense boundary for `useSearchParams()`.** Next.js 16 requires `useSearchParams` to be
  wrapped in `<Suspense>`. Login page splits into server `page.tsx` + client `login-form.tsx`.
- **`cookies()` is async.** Next.js 16 fully removed synchronous access. All `cookies()` calls
  use `await`.

## 5. Deferred / simplified

- None — all planned tasks delivered.

## 6. Known gaps

- Actual Neon Auth integration not tested end-to-end (requires valid `NEON_AUTH_URL`).
- `npm run dev` not started — build verification only.
