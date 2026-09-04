# QuerySales AI — Web Dashboard

The web frontend for **QuerySales AI**, an autonomous AI sales employee. Log in,
browse your leads, and watch the agent analyze a lead live — retrieving your
company knowledge (RAG), qualifying the lead, updating the CRM, and drafting
personalized outreach — with every step visible in a real-time timeline.

Built with **Next.js 16** (App Router, `proxy.ts`), React 19, TypeScript
(strict) and Tailwind CSS v4.

## Demo user

The dashboard ships with a ready-to-use demo account (created and seeded by
`python -m scripts.create_demo_user` in `salesops-agent-backend/`):

| Field    | Value                  |
| -------- | ---------------------- |
| Email    | `demo@querysales.demo` |
| Password | `Demo1234!`            |

The account is pre-seeded with:

- **5 leads** — including **Acme Manufacturing** (status `New`), the intended
  live-demo subject for *Analyze with QuerySales AI*
- **4 knowledge documents** — Manufacturing Solutions, an inventory case study,
  the product catalogue and the sales playbook (chunked, ready for embedding)

## Quick start

### Prerequisites

- Node.js **20.9+**
- The [backend](../salesops-agent-backend/) running on `http://localhost:8000`
  (`uvicorn main:app --reload --port 8000`)

### Setup

```bash
npm install
cp .env.example .env.local   # then fill in the values below
npm run dev                  # → http://localhost:3000
```

### Environment variables

| Variable              | Scope            | Description                                    |
| --------------------- | ---------------- | ---------------------------------------------- |
| `API_URL`             | Server-only      | FastAPI backend URL (default `http://localhost:8000`) |
| `NEON_AUTH_URL`       | Server-only      | Neon Auth (Better Auth) base URL               |
| `NEXT_PUBLIC_APP_URL` | Public           | This app's URL, e.g. `http://localhost:3000`   |

## Demo walkthrough

1. Open `http://localhost:3000` → you are redirected to **/login**
2. Sign in with the demo credentials above
3. The **Dashboard** shows the seeded KPIs (total/qualified leads, docs, runs)
4. Go to **Leads → Acme Manufacturing**
5. Click **Analyze with QuerySales AI** — a live timeline streams in as the
   agent observes the lead, searches your knowledge base, reasons about fit,
   updates the lead, and drafts outreach
6. Open **Agent Runs →** the finished run to inspect every phase, tool call
   (including the actual knowledge retrieved) and the outreach draft

> **Live agent analysis requires LLM + embedding keys.** Configure them once
> under **Settings** (per-user, AES-256-GCM encrypted) and use **Test
> Connection**; then process the knowledge documents so they get embedded.
> Until then, leads/knowledge/runs all work — only the agent run needs keys.

## Screens

| Route         | Purpose                                                              |
| ------------- | -------------------------------------------------------------------- |
| `/login`      | Email + password sign-in (Neon Auth)                                 |
| `/dashboard`  | KPI cards, lead overview, recent agent runs                          |
| `/leads`      | Lead list with search + status filter                                |
| `/leads/[id]` | Lead detail and the **Analyze with QuerySales AI** live timeline     |
| `/knowledge`  | Upload / delete knowledge documents, ingestion status                |
| `/runs`       | Agent run history                                                    |
| `/runs/[id]`  | Run detail — expandable phase timeline, tool calls, outreach drafts  |
| `/settings`   | LLM / embedding / email configuration status and connection tests   |

## Architecture notes

- **`proxy.ts`** (Next.js 16's replacement for `middleware.ts`) gates every
  page: unauthenticated visitors are redirected to `/login`, authenticated
  ones away from it.
- **The session JWT lives in an httpOnly cookie** (`qs_session`) — it is never
  readable from browser JavaScript. The browser talks only to Next.js route
  handlers; they attach the Bearer token server-side via `lib/api-client.ts`
  (`import 'server-only'`).
- **The live timeline is polling-based**: `components/agent/analysis-timeline-client.tsx`
  polls `/api/runs/{id}/events?after_sequence=N` each second and stops on
  completion or failure (the backend runs on Vercel's Python runtime, which
  buffers responses — SSE is not available).
- **No secrets in the browser**: API keys are stored server-side, encrypted,
  and only ever returned masked (e.g. `sk-••••1234`).

## Commands

| Command           | Description                                    |
| ----------------- | ---------------------------------------------- |
| `npm run dev`     | Start the dev server at `http://localhost:3000` |
| `npm run build`   | Production build (the authoritative type gate) |
| `npm run start`   | Serve the production build                     |
| `npm run lint`    | ESLint                                         |

## Related

- [`salesops-agent-backend/`](../salesops-agent-backend/) — FastAPI backend:
  agent, RAG pipeline, per-user config, and `scripts/create_demo_user.py`
- [`docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md) — the
  phase-by-phase build plan
