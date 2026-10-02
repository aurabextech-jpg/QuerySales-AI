# Feature — Autonomous web research for lead generation + SMTP send fix

**Date:** 2026-10-02 · **Branch:** main

## Why

A real chat ("find manufacturing companies in Karachi and qualify them") exposed five problems:

1. The agent asked the user which source to use, then asked them to configure Lead Source Sites,
   then asked them for each company's URL — the orchestrator prompt told it to.
2. `search_source_sites` matched query words in page text, so on a directory it returned the
   **filter menu** ("All Industries … Manufacturing … Karachi") and threw away every company link,
   because company names never contain the query words. Two companies were reported as Karachi
   leads; one (Crest LED) is in Lahore. The directory's own filter
   (`?industry=Manufacturing&location=Karachi`) returns **0 businesses** — the correct answer.
3. No tool could read a company website or search the web without a Google CSE key, so contacts
   could never be found and every lead scored "Low".
4. "The agent could not complete your request": every backend exception became a generic 502,
   including hitting the SDK's default 10-turn limit and LLM-provider errors.
5. **Mail → Approve & send** always failed (502) for this user: `mail_service._smtp_send` opened
   `SMTP_SSL` (implicit TLS) on the configured port 587, which speaks STARTTLS →
   `SSL: WRONG_VERSION_NUMBER`. The Settings "Test" button used STARTTLS, so it passed.

## What was built / changed

| File | Change |
|---|---|
| `mcp_tools/web_research.py` (new) | `web_search` (user's Google CSE if configured, else keyless DuckDuckGo HTML), `scrape_page` (one URL → compact fields: contacts, JSON-LD org data, rating, social, contact page, directory `listings`/`filters`/`pagination`), `research_companies` (≤8 companies in one call: find official site → homepage → contact page if needed → 0-100 score with `score_breakdown` and tier). SSRF guard on every hop, manual redirects, size caps, hard wall-clock deadlines. |
| `agent_core/orchestrator.py` | Three new tools on `LeadGenAgent`. Lead-gen prompt rewritten as DISCOVER → VERIFY → ENRICH → SCORE → REPORT, autonomous for read-only work. Orchestrator prompt: never ask which source; ask only before writes. Turn budgets: orchestrator 12, lead-gen 16. |
| `mcp_tools/lead_sources.py` | Results now include the page's `listings`, `filters`, `pagination`. |
| `api/endpoints/chat.py` | `MaxTurnsExceeded` → helpful chat reply; `APITimeoutError` / `APIStatusError` (401/429/…) → actionable 502 detail. |
| `querysales-web/app/api/chat/route.ts` | Passes the backend's non-500 `detail` through instead of always "could not complete". |
| `agent_core/model_factory.py` | LLM client `timeout=90s, max_retries=1` (SDK default 600 s × 3 attempts could hang a chat ~30 min). |
| `core/smtp.py` (new) | `open_smtp(host, port, timeout)`: port 465 → `SMTP_SSL`, else `SMTP` + mandatory `STARTTLS`. |
| `services/mail_service.py`, `api/endpoints/settings.py`, `api/endpoints/leads.py`, `mcp_tools/gmail.py` | All four SMTP call sites use `open_smtp`, so the Settings test exercises the same path as a real send. Mail send errors now distinguish auth rejection and refused recipient. |
| `tests/test_web_research.py` (new) | 11 offline tests: extraction, URL-decoding of `mailto:`/`tel:`, share-button filtering, directory structure, official-site picking, scoring, SSRF guard. |

## Token economy

The research tools return structured fields only, with empty values dropped. Measured on live
sites: the businessportal.pk directory page → 2,956 chars (listings + filters + pagination);
3 fully researched companies → ~2,600 chars total. Raw HTML for the same pages is 60k+ chars.
`include_text` (1,500-char excerpt) is opt-in.

## Verification

- `uv run pytest tests/test_web_research.py tests/test_lead_sources.py tests/test_mail_service.py -q`
  → **35 passed**.
- Live tool run (no LLM): Crest LED → `crestled.com`, `info@crestled.com`, `03014086773`,
  4 socials, `city_match: false` (Lahore), score 75 High. Home Innovators → 3 emails, phones,
  socials, 65 Medium. Engro → `engropolymer.com` found; site has a broken TLS chain, reported as
  such (verification is never disabled).
- SSRF: `http://169.254.169.254/…`, `127.0.0.1`, `10.0.0.5`, `file://`, `ftp://` all rejected.
- SMTP against the user's real server `smtp.titan.email`: old `SMTP_SSL:587` →
  `SSLError WRONG_VERSION_NUMBER`; `open_smtp` 587 → STARTTLS TLSv1.2 OK; 465 → SSL OK;
  login with saved credentials → `235` (authenticated; nothing sent).
- `npm run build` passes; `eslint app/api/chat/route.ts` clean.

## Decisions

- **Keyless search fallback is not a shared credential** (rule §3.4 holds): DuckDuckGo's HTML
  endpoint needs no key. A user with Google CSE configured gets Google first; quota/key errors
  fall back to DuckDuckGo rather than failing the research.
- **Deterministic score in the tool, fit judgement in the LLM.** The tool scores contact
  completeness + reputation with published weights; the agent may adjust ±15 for fit and must
  say why. Explainable and stable across runs.
- **User-pasted URLs need no Settings step.** `scrape_page` reads any public URL the user gives;
  Lead Source Sites remains the place for sources they want searched every time.
- **Port decides TLS mode** (465 implicit, otherwise STARTTLS, never plaintext).

## Update — find_leads, rate limits, token budget (same day)

A real-LLM run exposed the binding constraint: the user's LLM is **Groq free tier
`openai/gpt-oss-20b` — 8,000 tokens/minute, 200,000 tokens/day**. One "find leads" request cost
~12-13k tokens (4 model calls), so every run hit 429s; a 429 inside the lead-gen sub-agent was
swallowed into a tool error and the orchestrator re-ran the whole search (3x the spend). Test
runs exhausted the daily quota. DuckDuckGo also began serving bot challenges (HTTP 202 +
"anomaly") after ~25 test queries.

| File | Change |
|---|---|
| `mcp_tools/lead_finder.py` (new) | `find_leads(industry, city, source_url?)`: discover (directory with its own filters → web search for company sites, skipping lead-list sellers/listicles) + research + score in **one tool call**. |
| `agent_core/orchestrator.py` | `find_leads_tool` sits on the **orchestrator** too: "find X in Y" is 2 model calls instead of 4. All four prompts rewritten compactly; six tool docstrings trimmed; `failure_error_function=None` on every sub-agent so provider errors end the run instead of triggering re-delegation. History: system messages dropped (the system prompt was being sent twice per call), last 8 messages, each clipped to 1,200 chars. |
| `api/endpoints/chat.py` | No longer injects the system prompt into the message list. |
| `agent_core/model_factory.py` | `timeout=90s`, `max_retries=3` (retries honour 429 `retry-after`). |
| `mcp_tools/web_research.py` | `SearchBlocked` detection → reason `search_blocked` with a fix-it message; aggregator domains added to the non-official list; result trimmed (description 160 chars, ≤2 sources, LinkedIn/Facebook only). |
| `tests/test_lead_finder.py` (new) | 4 tests: title→name, filter matching, challenge-page detection, directory-with-0-results. |

Fixed cost per model call (≈ chars/4, instructions + tool schemas):

| Agent | Before | After |
|---|---|---|
| Orchestrator | ~1,730 + prompt duplicated in input (~1,450) | ~841 |
| LeadGen | ~2,741 | ~1,421 |
| CRM | ~1,391 | ~999 |
| Outreach | ~1,243 | ~808 |

Researched company in a tool result: ~330 → ~190 tokens.
Verification: `pytest` 39 passed; strict tool schemas build; `_build_input` checked by hand.
**Not yet verified:** a complete real-LLM run with the compact prompts — blocked by the Groq daily
quota; to be re-run with the user's new key.

## Known gaps / follow-ups

- DuckDuckGo may rate-limit bursts; `research_companies` caps concurrency at 4 and degrades to a
  per-company note. For heavy use, configure Google Custom Search.
- JS-rendered sites (content injected client-side) yield little; no headless browser — deliberate
  (50 MB lambda).
- Ratings come from JSON-LD or search snippets only; without Google Places many leads have none.
- `COMPANY_DEADLINE` (40 s) includes time waiting for the concurrency gate.
