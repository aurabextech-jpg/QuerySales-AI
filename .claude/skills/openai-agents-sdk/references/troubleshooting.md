# Troubleshooting

The SDK's errors are frequently misleading — an auth failure in the **tracing
exporter** surfaces as a `400` on the **model call**. Work the decision tree in
order rather than debugging the reported error directly.

---

## Decision tree

```
Agent run fails
│
├─ Error mentions Authorization / 401 / tracing?
│  └─ Is the API key from platform.openai.com?
│     ├─ No  → set_tracing_disabled(True) before any agent init.   ← most common
│     └─ Yes → Key is invalid, expired, or lacks the model. Verify with a raw curl.
│
├─ Error mentions response_format / json_schema?
│  └─ output_type= is set. Remove it; use prompt-instructed JSON.
│
├─ Error is 404, or names /responses?
│  └─ set_default_openai_api("chat_completions") at import.
│
├─ Error is MaxTurnsExceeded?
│  └─ Model is looping on tools. Raise max_turns, or set max_turns=1
│     for single-shot extraction, and check tool descriptions for ambiguity.
│
├─ Error is a JSONDecodeError on final_output?
│  └─ Model wrapped JSON in prose or fences. Harden _extract_json,
│     log raw_head, and tighten the instructions.
│
└─ Error is a connection/timeout?
   └─ base_url wrong or provider down. Curl the endpoint directly.
```

---

## The cause chain behind the misleading 400

1. A non-OpenAI key is configured for the model client.
2. The SDK initializes its tracing exporter, which targets OpenAI's servers.
3. The exporter authenticates with the ambient OpenAI credential and gets `401`.
   → `WARNING: OPENAI_API_KEY is not set, skipping trace export`
   → `ERROR: Tracing client error 401`
4. Auth state is now poisoned for the run.
5. The model call fails with
   `openai.BadRequestError: 400 - Missing or invalid Authorization header`.

The 400 names the model call, but the fault is at step 3. `set_tracing_disabled(True)`
— placed at module import, before any `Agent` is constructed — resolves the chain.

---

## Error table

| Error | Cause | Fix |
|-------|-------|-----|
| `400 Missing or invalid Authorization header` | Tracing enabled with non-OpenAI key | `set_tracing_disabled(True)` at import |
| `Tracing client error 401` | Same | Same |
| `WARNING: OPENAI_API_KEY is not set, skipping trace export` | Same (benign alone, precedes the 400) | Same |
| `'response_format.type' : value is not one of the allowed values ['text','json_object']` | `output_type=` on a provider without json_schema | Drop `output_type`; prompt-instructed JSON |
| `404` / unknown endpoint `/responses` | Responses API against a Chat-Completions-only provider | `set_default_openai_api("chat_completions")` |
| `ModuleNotFoundError: agents` | Package not installed | `pip install openai-agents` |
| `AsyncOpenAI has no such method` | Imported from `openai`, not `agents` | `from agents import AsyncOpenAI` |
| `MaxTurnsExceeded` | Tool loop never converges | Raise `max_turns`; clarify tool descriptions; `max_turns=1` for extraction |
| `json.JSONDecodeError` | Fences/prose around the JSON | Harden `_extract_json`; log the raw head |
| `401` from the provider | Bad or wrong-provider key | Decrypt and verify; confirm key matches `base_url` |
| `model_not_found` / `404` on model | Model id not valid for this provider | Use the provider's exact id (Groq and OpenRouter differ) |
| Empty `final_output` | `max_tokens` too low; output truncated | Raise `max_tokens`; log `usage` |
| `400` only when images are attached | Provider or model lacks vision | Catch and retry text-only (see `structured-output.md`) |

---

## Diagnostics

**Confirm the installed version and that imports resolve:**

```bash
python -c "import agents; print(agents.__version__ if hasattr(agents,'__version__') else agents.__file__)"
```

**Verify a provider/base_url/model without touching the app:**

```bash
python .claude/skills/openai-agents-sdk/scripts/check_provider.py \
  --base-url https://api.groq.com/openai/v1 --model llama-3.3-70b-versatile
```

**Bypass the SDK entirely to isolate credentials from SDK config:**

```bash
curl -sS "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"MODEL","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

If curl succeeds and the SDK fails, the problem is SDK configuration (tracing, API
surface, imports) — not the credential.

**See what the model actually returned** when parsing fails — log a bounded head of
the raw output, never the whole body:

```python
logger.info("raw_head=%r", str(result.final_output or "")[:200])
```

---

## In this repo specifically

Symptom-to-source map for `agent-service/`:

| Symptom | Check |
|---------|-------|
| Every clinic fails | `set_tracing_disabled` / `set_default_openai_api` missing from the agent module |
| One clinic fails | That clinic's `ai_settings` row — `base_url`, `model`, `api_key_encrypted` |
| `reason: "no_api_key"` | `api_key_encrypted` is null → `build_model_from_settings` returned `None` |
| `reason: "ai_disabled"` | `ai_settings.enabled` is false (the kill switch) |
| `reason: "agent_error"` | The agent raised; the real error is in `logger.exception` server-side |
| Decryption error | `SOCIAL_TOKEN_ENCRYPTION_KEY` differs between Next.js and the agent service — they must match exactly |
| Next.js gets 401 from the service | `AI_AGENT_SERVICE_TOKEN` mismatch across the two deployments |
| Summaries silently heuristic | `AI_AGENT_BACKEND_URL` unset → `isAgentBackendConfigured()` false. By design, not a bug |

Routes deliberately return a `reason` instead of raising, so a failure degrades to
the heuristic path rather than breaking the call flow. When a user reports "AI
stopped working," check `reason` values in the logs first — several are intentional.
