# Inbound Email & Gmail-style Mail Workspace — Design

Date: 2026-09-04 · Status: Approved by user in conversation
Scope: `salesops-agent-backend/` (FastAPI) + `querysales-web/` (Next.js 16)

## 1. Goal

The sales agent can read a user's **incoming** email, generate **editable reply
drafts** for user-selected messages, and send an approved draft through the
user's own SMTP account — presented in a **Gmail-style Mail workspace**
(Inbox / Sent / Drafts / Trash).

Today the email subsystem is outbound-only: `UserEmailConfig` stores per-user
SMTP credentials (AES-256-GCM), `mcp_tools/gmail.py:send_email` sends via
global env vars, and `OutreachDraft` holds lead-outreach drafts. Nothing
receives mail. This feature adds reception without touching those paths.

## 2. Approved decisions

| # | Decision | Rationale |
|---|----------|-----------|
| E1 | Inbound connection = **IMAP**, derived from the user's existing SMTP config (no new settings fields). | User chose "Derive from SMTP". Gmail: `smtp.gmail.com → imap.gmail.com`, port 993 (IMAPS). Unknown hosts: replace leading `smtp.` with `imap.`; if login fails, return an actionable error naming the derived host. |
| E2 | **Manual sync** ("Sync inbox" button). No cron/background worker. | Vercel serverless cannot host reliable background pollers; demo-safe. |
| E3 | **User selects messages → "Generate drafts"**. The agent never auto-drafts on sync. | User requirement: drafts only for emails the user picks. |
| E4 | **Approve & send** sends the edited draft via the user's resolved SMTP config and stores a copy in Sent. | User chose "Send via SMTP". |
| E5 | **Gmail-style UI**: folder rail (Inbox/Sent/Drafts/Trash), selectable message list, detail pane with reply editor. | User requirement. |
| E6 | Sync never mutates the remote mailbox (no SEEN/flag changes, no deletes). | Read-only reception; user's real inbox stays untouched. |

## 3. Data model (one Alembic migration)

Both tables user-scoped (`user_id` FK → `users.id`, indexed). Follows
`db/models.py` conventions (`generate_uuid` PK, `_utcnow` timestamps).

### `mail_messages`
| Column | Type | Notes |
|---|---|---|
| id | String PK | `generate_uuid` |
| user_id | String FK users.id | indexed, NOT NULL |
| direction | String | `inbound` \| `outbound` |
| imap_uid | Integer, nullable | IMAP UID; dedup key for inbound sync (unique per user+uid) |
| from_addr | String | |
| to_addrs | String | comma-joined |
| subject | String | default `""` |
| body_text | Text | plain-text extraction (first text/plain part; fallback stripped text/html); capped at 20 000 chars |
| received_at | DateTime | inbound: mail Date header; outbound: send time |
| read_at | DateTime nullable | UI read state (local only) |
| trashed_at | DateTime nullable | Trash folder membership |
| in_reply_to_id | String FK mail_messages.id nullable | threading: reply → original inbound message |

Indexes: `(user_id, direction, trashed_at)`, unique `(user_id, imap_uid)`
(partial — only rows where imap_uid IS NOT NULL; enforced in service layer if
the partial index is awkward: check-then-insert inside the sync transaction).

### `mail_drafts`
| Column | Type | Notes |
|---|---|---|
| id | String PK | |
| user_id | String FK users.id | indexed |
| inbound_message_id | String FK mail_messages.id nullable | message being replied to |
| run_id | String FK workflow_runs.id nullable | agent run that created it |
| to_addr | String | |
| subject | String | |
| body | Text | editable |
| status | String | `draft` \| `sent` \| `discarded` |
| sent_message_id | String FK mail_messages.id nullable | outbound copy created on send |
| created_at / updated_at | DateTime | |

`OutreachDraft` (lead outreach) is **not** merged into this feature; it stays
in the lead/run flow.

## 4. Backend

### 4.1 `services/mail_service.py` (new package `services/`)
Pure infrastructure, no agent logic:
- `derive_imap_host(smtp_host) -> str` — E1 mapping.
- `sync_inbox(user_id, db) -> SyncResult` — resolve email config
  (`core/user_config.py:resolve_email_config`), IMAPS connect + login
  (`email_address` + decrypted `smtp_password`), `SELECT INBOX`, fetch unseen-by-us
  messages (UIDs not already stored) up to **50 per sync**, newest first; parse
  headers + body; insert `mail_messages(direction=inbound)`. Runs in a
  thread executor (`asyncio.to_thread`) — `imaplib` is blocking. Never sets
  flags (E6). Returns `{synced, skipped_duplicate, failed}` + per-message
  errors (no bodies in errors).
- `send_reply(user_id, draft, db) -> MailMessage` — SMTP send via
  `smtplib.SMTP_SSL(resolved.smtp_host, resolved.smtp_port)` with resolved
  per-user credentials (NOT `mcp_tools/gmail.py`, which is env-based),
  `From: email_address`, proper `In-Reply-To`/`References` when replying;
  inserts outbound `mail_messages` row (in_reply_to_id set), marks draft
  `sent` + `sent_message_id`. On SMTP failure: draft stays `draft`, raise
  `MailSendError` with generic message; real cause logged server-side only.
- Body/subject decoding via `email.policy.default`; secrets and raw bodies
  never logged (AGENTS.md §3.3).

### 4.2 `agent_core/inbound_reply_agent.py`
New single agent (pattern: `agent_core/sales_agent.py`), `run_inbound_reply_agent(
user_id, message_ids, db) -> run_id + draft ids`:
- Creates `WorkflowRun(workflow_type="inbound_reply")`; events flow through the
  existing `DatabaseTracingProcessor` so `/api/runs/{id}/events` polling works.
- Per-user LLM via `resolve_llm_config` (no global client, §3.4).
- Tools: existing `search_knowledge` (reuse from `agent_core/sales_tools.py`) +
  new `create_reply_draft(to, subject, body)` tool that inserts `mail_drafts`
  (status `draft`, run_id set). The agent must call it once per input message.
- Prompt: professional sales reply in the user's voice; may ground on
  knowledge; must address the sender's actual question; never promise
  discounts/contracts not in knowledge.
- Cap: **max 5 messages per request** (serverless timeout budget); each draft
  = ~1 LLM turn.
- Agent never sends mail and never touches leads.

### 4.3 `api/endpoints/mail.py` (router prefix `/api/mail`)
All handlers: `user = Depends(get_current_user)`, `db = Depends(get_db)`;
every query filters `user_id`; 404 for other users' rows (§3.2). Pydantic
request/response models for every body.

| Method & path | Behavior |
|---|---|
| POST `/sync` | `mail_service.sync_inbox`; returns `SyncResult` |
| GET `/messages?folder=inbox\|sent\|trash` | folder = inbound-not-trashed / outbound-not-trashed / trashed (any direction); ordered newest first; list shape (no full body) + `unread_count` and per-folder counts |
| GET `/messages/{id}` | full message; sets `read_at` for inbound |
| POST `/messages/{id}/unread` | clears `read_at` |
| POST `/messages/{id}/trash` | sets `trashed_at` |
| POST `/messages/{id}/restore` | clears `trashed_at` |
| DELETE `/messages/{id}` | permanent delete; **only when trashed** (else 409) |
| POST `/drafts/generate` `{message_ids: [...]}` (1–5, must be user's inbound) | runs agent synchronously; returns `{run_id, draft_ids, errors[]}` |
| GET `/drafts` | status=`draft`, newest first (Drafts folder) |
| GET `/drafts/{id}` | single draft |
| PUT `/drafts/{id}` `{to_addr?, subject?, body?}` | edit (only while status=`draft`) |
| POST `/drafts/{id}/send` | approve & send (E4); returns sent message id |
| POST `/drafts/{id}/discard` | status=`discarded` (leaves Trash folder; hidden from Drafts) |

Registration in `main.py`: `app.include_router(mail_ep.router, prefix="/api/mail", tags=["mail"])`.

### 4.4 Errors
`ConfigurationMissing` (no email config) → existing 400 handler with
actionable message ("Settings → Email"). IMAP auth/derive failures → 502 with
generic-but-actionable detail (e.g. "Could not sign in to imap.example.com
with your saved email password"). Never leak passwords/hosts of other users.

## 5. Frontend (`querysales-web/`)

### 5.1 Routes & components
- `app/(dashboard)/mail/page.tsx` — server component: fetch folder list +
  first folder's messages via internal API; renders client shell.
- `app/(dashboard)/mail/mail-client.tsx` — the workspace (client): folder rail,
  list, detail/editor panes; selection state; polling of
  `/api/runs/{id}/events` while drafts generate (existing pattern, D6).
- `app/(dashboard)/mail/components/`: `folder-rail.tsx`, `message-list.tsx`,
  `message-view.tsx`, `draft-editor.tsx` (each < 300 lines).
- Sidebar (`components/sidebar.tsx`): new NAV item **Mail** (`/mail`, icon
  `✉️`) between Dashboard and Leads.
- Loading / success / error / empty states on every folder list, detail and
  editor (§3.5). Empty Inbox shows a "Sync inbox" call-to-action.

### 5.2 Proxy routes (server-side Bearer attach, D4)
- `app/api/mail/[...segments]/route.ts` — catch-all forwarding GET/POST/PUT/
  DELETE + query + JSON body to `${API_URL}/api/mail/...`, surfacing FastAPI
  `{detail}` like the settings proxies do.
- **Do not modify** `app/api/settings/[section]/test/route.ts` (user-edited
  file; unchanged by this feature).

### 5.3 Types
`lib/types.ts`: `MailMessage`, `MailFolder`, `MailCounts`, `MailDraft`,
`SyncResult`, `GenerateDraftsResult`. No `any`.

## 6. Security invariants (AGENTS.md §3.2/§3.3)
- Every mail/draft row carries `user_id` from the JWT; all SELECT/UPDATE/
  DELETE filter it; cross-user access → 404.
- IMAP/SMTP password decrypted only inside `mail_service`, at use time; never
  in responses, logs, traces, or `NEXT_PUBLIC_*`.
- Email bodies stored in Postgres (user's own data) but never echoed into
  AgentEvent payloads beyond a short subject/sender summary.

## 7. Test plan
1. `alembic upgrade head` clean on the Neon DB.
2. Backend unit-ish: `derive_imap_host` cases (gmail, custom, no-prefix).
3. E2E via httpx against local uvicorn + Next dev server:
   login → POST /api/mail/sync (real Gmail app-password demo account if
   available; otherwise assert clean 502 error shape with bad creds) →
   messages list → generate drafts (real LLM key from Settings) → edit draft
   → send → Sent folder contains copy → trash/restore/delete-permanent.
4. Isolation: user B's token cannot read user A's messages/drafts (404).
5. `npm run build` zero errors; manual UI pass of all four folders + editor.

## 8. Out of scope (P2)
Attachments, scheduled polling, spam folder, labels/stars, search, threading
UI beyond in_reply_to linkage, provider-side Drafts folder, merging
OutreachDraft into the Mail workspace, mobile-app parity.
