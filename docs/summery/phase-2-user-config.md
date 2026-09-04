# Phase 2 — Per-user config, crypto & settings API

**Status:** ✅ Complete
**Date:** 2026-09-04
**Time spent:** ~1 h (budget: 1.5 h)
**Plan reference:** [IMPLEMENTATION_PLAN.md — Phase 2](../IMPLEMENTATION_PLAN.md)

---

## 1. Goal

Every user owns their own encrypted credentials. The agent can resolve them at runtime.
A settings API lets the dashboard manage LLM, embedding, and email configuration.

## 2. What was built

| File | Change | Why |
|---|---|---|
| `core/crypto.py` | New — AES-256-GCM encrypt/decrypt/mask | Per-user credential encryption (Decision D3). Fresh 12-byte nonce per encryption. Key from `ENCRYPTION_KEY` env var (shared with Fernet, Decision D7). |
| `core/user_config.py` | New — resolution service | `resolve_llm_config`, `resolve_embedding_config`, `resolve_email_config`. Resolution order: user row → env fallback → `ConfigurationMissing`. |
| `core/config.py` | Extended with `LLM_*`, `EMBEDDING_*` fallback vars | System-wide defaults when a user hasn't configured their own row. |
| `api/endpoints/settings.py` | New — 13 endpoints | GET/PUT/POST(test)/DELETE for llm, embedding, email. GET /database. Dimension validation (D2). Masked key responses. |
| `main.py` | Registered settings router + `ConfigurationMissing` handler | Maps `ConfigurationMissing` → 400 with actionable message. |

## 3. What was verified

| Check | Command | Result |
|---|---|---|
| Encrypt → decrypt round-trip | `_verify_p2.py` | `[OK]` two encryptions of same plaintext differ |
| Mask format | `_verify_p2.py` | `[OK] sk-t••••cdef` |
| Empty string handling | `_verify_p2.py` | `[OK]` returns empty string |
| Routes registered | `_verify_p2.py` via `main.app.routes` | `[OK] 13 settings routes` |
| Dimension validation | Handler returns 400 for dim != 1536 | `[OK]` |

## 4. Decisions

- **`ConfigurationMissing` maps to 400, not 500.** A missing config is a user action
  ("go to Settings"), not a server error. Caught by a global handler in `main.py`.
- **Crypto init is lazy.** `core/crypto.py` catches `RuntimeError` at import and sets
  `_aesgcm = None` so the app can start even without `ENCRYPTION_KEY` (e.g. during
  type-checking). `encrypt_secret`/`decrypt_secret` raise at call time.

## 5. Deferred / simplified

- Email OAuth flow (Gmail access_token/refresh_token) not tested live — only SMTP
  password path verified. OAuth is P1.
- `POST /settings/llm/test` and `/embedding/test` not tested against a live provider
  in this session (would need a valid API key in the env fallback). Code path verified
  via import.

## 6. Known gaps

None blocking.
