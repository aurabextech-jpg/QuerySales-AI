# Feature — Inbound Email & Mail Workspace

**Status:** ⚠️ Complete with known gaps (code done + statically verified; live E2E blocked by missing local `.env`)
**Date:** 2026-09-04
**Time spent:** multi-session continuation (not separately tracked)
**Plan reference:** [2026-09-04-inbound-email-mail-workspace.md](../superpowers/plans/2026-09-04-inbound-email-mail-workspace.md)

---

## 1. Goal

Let the agent read a user's incoming email over IMAP, generate one **editable** reply draft per
selected message, and send it over SMTP only after the user approves — all surfaced in a Gmail-style
Mail workspace with Inbox / Sent / Drafts / Trash folders.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `salesops-agent-backend/db/models.py` | Modified | Added `MailMessage` + `MailDraft` ORM models, both `user_id`-scoped; folder index `ix_mail_messages_user_dir_trashed`. |
| `salesops-agent-backend/alembic/versions/9a4f092a31fb_add_mail_workspace_tables.py` | Created | Migration for `mail_messages` + `mail_drafts`; hand-trimmed a spurious autogen `drop_index` of the pgvector IVFFLAT index. |
| `salesops-agent-backend/services/mail_service.py` | Created | IMAP **read-only** inbox sync (dedup by `imap_uid`), SMTP send, body extraction (text/plain → tag-stripped html), and `derive_imap_host` (SMTP→IMAP). |
| `salesops-agent-backend/tests/test_mail_service.py` | Created | 7 unit tests for the pure helpers (`derive_imap_host`, `extract_body_text`) — no network, no DB. |
| `salesops-agent-backend/agent_core/inbound_reply_agent.py` | Created | `run_inbound_reply_agent` (one run per batch, `workflow_type="inbound_reply"`) + `create_reply_draft_tool`; reuses `search_knowledge` and the shared tracing/events layer. |
| `salesops-agent-backend/api/endpoints/mail.py` | Created | 14 `/api/mail` endpoints: sync, folder list, message detail, unread/trash/restore/delete, draft generate/create/list/get/edit/send/discard. |
| `salesops-agent-backend/main.py` | Modified | Imported and registered the mail router. |
| `querysales-web/lib/types.ts` | Modified | Mail TS types mirroring the Pydantic models (`MailMessageListItem`, `MailFolderCounts`, `MailListResponse`, `MailMessageDetail`, `MailDraft`, `SyncResult`, `GenerateDraftsResult`). |
| `querysales-web/app/api/mail/[...segments]/route.ts` | Created | Catch-all proxy forwarding browser calls to backend `/api/mail/*` with the httpOnly-cookie JWT (Decision D4). |
| `querysales-web/components/sidebar.tsx` | Modified | Added the **Mail** nav item (`MailIcon`). |
| `querysales-web/app/(dashboard)/mail/components/folder-rail.tsx` | Created | Inbox/Sent/Drafts/Trash rail with live counts. |
| `querysales-web/app/(dashboard)/mail/components/message-list.tsx` | Created | Selectable list + folder-context toolbar + loading/empty/error states. |
| `querysales-web/app/(dashboard)/mail/components/message-view.tsx` | Created | Full message pane with reply / trash / restore / delete-forever. |
| `querysales-web/app/(dashboard)/mail/components/draft-editor.tsx` | Created | Editable draft: Save · Approve & send · Discard. |
| `querysales-web/app/(dashboard)/mail/mail-client.tsx` | Created | Workspace state machine: folder switching, selection, sync, generate + `AnalysisTimeline`, draft lifecycle. |
| `querysales-web/app/(dashboard)/mail/page.tsx` | Created | Server component that seeds the initial inbox view (`force-dynamic`). |
| `AGENTS.md` | Modified | §7 project-memory entry + §8 Decision D12. |
| `docs/summery/feature-inbound-email-mail-workspace.md` | Created | This summary. |

Commits (on `main`): `2513758` models+migration · `30e3d3c` carried the mail_service files (parallel
refactor sweep) · `e316cb6` agent · `06efc18` endpoints · `1b2da6b` frontend types/proxy/nav ·
`67d7c96` workspace UI.

## 3. What was verified — and how

| Check | Command / action | Result |
|---|---|---|
| Mail unit tests | `python -m pytest tests/test_mail_service.py -v` | ✅ **7 passed** in 1.28s |
| Backend imports + router wired | `python -c "…import main; [r for r in main.app.routes if '/mail' in r.path]…"` (placeholder `DATABASE_URL`/`ENCRYPTION_KEY`, no connection made) | ✅ `MAIL_ROUTE_COUNT 14` — all `/api/mail/*` paths + methods correct |
| Frontend type gate | `npm run build` | ✅ Compiled successfully; TypeScript finished with no errors; `ƒ /mail` and `ƒ /api/mail/[...segments]` present in the route manifest |
| Frontend lint | `npm run lint` | ✅ **0 errors**, 1 warning (see §7) |
| Migration applies | `alembic upgrade head` (Task 1) | ✅ head `9a4f092a31fb`; import smoke clean |

Acceptance criteria from the plan:

- [x] Task 6 build gate: `npm run build` → zero errors.
- [x] Backend routes register and modules import cleanly.
- [x] Mail service pure helpers unit-tested green.
- [ ] **Task 7 Steps 1–4 (live E2E): NOT executed** — this workspace has **no `salesops-agent-backend/.env`**, so there is no `DATABASE_URL`, `ENCRYPTION_KEY`, Neon Auth JWKS, seeded user, or IMAP/SMTP credential. `db/session.py` builds the engine at import and raises on an empty `DATABASE_URL`, so the servers cannot boot here. This is an environment limitation, not a code defect; the walkthrough must be run in a configured environment (see §7).

## 4. Decisions made

| Decision | Alternatives considered | Why this one |
|---|---|---|
| IMAP host derived from SMTP; read-only sync; drafts stored locally and sent only on approval (logged as **D12**). | Separate IMAP credential field; mutate the provider mailbox directly; auto-send. | One email config, per-user isolation (rule §3.2), human-in-the-loop — see [AGENTS.md §8](../../AGENTS.md#8-decision-log). |
| Folder-rail active state uses a **neutral** `bg-muted text-fg`, not lime. | Lime `bg-signal text-on-signal` (matches the sidebar). | Rule 2: the screen's one lime CTA is **Generate drafts**; a second lime region would compete with it. |
| Replaced the plan's `LoadingState` with an inline pulsing-dot block. | Import `LoadingState` from `states.tsx`. | `states.tsx` exports only `EmptyState`/`ErrorState`/`ErrorBanner` — `LoadingState` does not exist and would fail the build. The pulsing `bg-signal animate-signal-pulse` dot matches `analysis-timeline-client.tsx`. |
| Dropped the plan's outer `<Card>` wrapper around `<AnalysisTimeline>`. | Keep the wrapper. | `AnalysisTimeline` already renders a `Card`; wrapping it produced a card-in-card. |
| Remapped the plan's design tokens to the real theme. | Use the plan's classes verbatim. | Plan used `text-text*`, `text-error`, `bg-primary-muted`, `bg-surface-highlight` — none exist in `globals.css`. Mapped to `text-fg*`, `text-danger`, `bg-muted`, `hairline-b/t`, `divide-line`. |
| Kept the client `mailFetch` hard `window.location.href="/login"` on 401. | `useRouter().push()`. | `mailFetch` is module-level (no router hook); a full-page nav is the intended hard reset of stale client state. Yields one benign lint warning (§7). |

## 5. Deferred or simplified

| Item | Deferred to | Reason |
|---|---|---|
| Attachments (fetch/store/render) | P1 | Out of scope for the demo; only text bodies are synced. |
| Scheduled / automatic inbox polling | P1 | Sync is a manual button; a background scheduler adds infra the demo doesn't need. |
| Provider-side Drafts folder (write drafts back to IMAP) | P2 | Drafts live only in our Postgres — simpler and keeps isolation. |
| Conversation / threading view | P2 | `in_reply_to_id` and RFC-822 `message_id` are stored but not rendered as threads. |
| Live E2E walkthrough (plan Task 7 Steps 1–4) | Blocked (environment) | Requires a configured `.env` + seeded users + real SMTP/IMAP creds. |

## 6. Discovered — affects later phases

- **UI plans must read `globals.css` + `states.tsx` before writing Tailwind.** The plan's Task 6 code
  used a token vocabulary (`text-text`, `bg-surface-highlight`, `bg-primary-muted`) that does not
  exist in this theme, and imported a `LoadingState` primitive that was never created. Both would
  have failed `npm run build`. Any future UI task should copy tokens from `globals.css` and the nav
  idiom from `components/sidebar.tsx`.
- **The backend cannot be imported without `DATABASE_URL`.** `db/session.py` constructs the engine at
  module import and raises `RuntimeError` on an empty URL. Static verification (route registration,
  import health) therefore needs placeholder env vars; a real run needs the Neon string.
- **The Write tool reports a false "save failed" on paths with special characters** (`(dashboard)`,
  `[...segments]`) but writes the file correctly. Always confirm with a follow-up Read.
- **`git add "path/[...segments]"` treats `[...]` as a glob char-class** — add the parent directory
  instead. Parentheses in `(dashboard)` are literal and safe.

## 7. Known gaps & follow-ups

- **Live E2E not run.** When a configured environment is available, execute plan Task 7 Steps 1–4:
  boot backend (`uvicorn main:app --reload --port 8000`) + frontend (`npm run dev`), log in as
  `demo@querysales.demo` / `Demo1234!`, ensure that user has **SMTP configured in Settings → Email**,
  then: `POST /api/mail/sync` → `GET /messages?folder=inbox` → select → `POST /drafts/generate` →
  poll `GET /api/runs/{id}/events` to COMPLETE → `GET /drafts` → `PUT /drafts/{id}` (edit) →
  `POST /drafts/{id}/send` → trash/restore/delete. Then the isolation probe with a second user's
  cookie (`GET /api/mail/messages/{userA_id}` → 404, `GET /api/mail/drafts/{userA_id}` → 404).
- **Lint warning** `@next/next/no-location-assign-relative-destination` at `mail-client.tsx:30`
  (`window.location.href="/login"`). Intentional (see §4). AGENTS.md's gate is "zero errors", met.
- **Isolation is enforced in code** (every mail query filters `WHERE user_id = <auth>`; cross-user
  reads 404, not 403) but was not runtime-probed here.

## 8. Memory updates applied

- [x] [AGENTS.md §7 Project Memory](../../AGENTS.md#7-project-memory) — inbound-email/Mail-workspace entry
- [x] [AGENTS.md §8 Decision Log](../../AGENTS.md#8-decision-log) — **D12**
- [ ] [AGENTS.md §9 Phase Status](../../AGENTS.md#9-phase-status) — N/A: this is a standalone feature, not one of the numbered phases 0–10.

## 9. Next phase

None. The feature is code-complete and statically verified; the only outstanding work is the live
E2E + isolation walkthrough (§7), which requires a configured runtime environment.
