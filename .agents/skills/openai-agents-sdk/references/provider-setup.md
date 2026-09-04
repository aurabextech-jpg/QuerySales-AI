# Provider Setup

How to point the OpenAI Agents SDK at any OpenAI-compatible Chat Completions endpoint.

> Verify the current API against context7 before relying on this file:
> `mcp__context7__query-docs` on `/websites/openai_github_io_openai-agents-python`.

---

## The three initialization patterns

### A. Model name string — real OpenAI only

```python
agent = Agent(name="Assistant", model="gpt-4.1")
```

Uses the default OpenAI provider and the default API surface. Only valid with a
`platform.openai.com` key. Tracing works.

### B. Explicit model + client — the pattern this repo uses

```python
from agents import AsyncOpenAI, OpenAIChatCompletionsModel

client = AsyncOpenAI(api_key=api_key, base_url=base_url)
model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
agent = Agent(name="Assistant", model=model)
```

Per-request provider selection. Required when the provider is chosen at runtime
(here: from each clinic's `ai_settings` row). **Use this.**

### C. Global default client — single provider for the whole process

```python
from agents import set_default_openai_client, AsyncOpenAI, Agent

set_default_openai_client(AsyncOpenAI(api_key=key, base_url=url))
agent = Agent(name="Assistant", model="llama-3.3-70b-versatile")  # string now works
```

Simplest when one provider serves the whole process. **Wrong for this repo** —
providers are per-clinic, and a global default would leak one tenant's config
into another's request.

---

## `OpenAIChatCompletionsModel`

```python
OpenAIChatCompletionsModel(
    model: str,                                  # required — provider's model id
    openai_client: AsyncOpenAI | None = None,    # required in practice for non-OpenAI
    model_settings: ModelSettings | None = None, # optional
)
```

`ModelSettings` carries `temperature`, `max_tokens`, `top_p`, `tool_choice`, and
`extra_args`. It can be set on the model **or** on the `Agent`; this repo sets it
on the `Agent` so tuning stays next to the instructions.

---

## Import source matters

| Import | Package | Use |
|--------|---------|-----|
| `from agents import AsyncOpenAI` | `openai-agents` | ✅ Always, inside SDK code |
| `from openai import AsyncOpenAI` | `openai` | Raw API calls only, outside the SDK |

`agents` re-exports `AsyncOpenAI` to guarantee a compatible version. Mixing the two
in one process produces confusing type and method errors.

---

## API surface selection

The SDK defaults to OpenAI's **Responses API**. Almost no third-party provider
implements it — they expose Chat Completions only.

```python
from agents import set_default_openai_api
set_default_openai_api("chat_completions")
```

Call this at module import, before any agent runs. Symptom when missing: `404` on
a `/responses` path, or an error naming an unknown endpoint.

---

## Tracing

The SDK uploads traces to OpenAI by default. A non-OpenAI key cannot authenticate
there, and the resulting failure often surfaces as a misleading `400` on the model
call. Pick one of three:

```python
# A. Disable entirely — what this repo does
from agents import set_tracing_disabled
set_tracing_disabled(True)

# B. Keep tracing, authenticate it separately with a real OpenAI key
from agents import set_tracing_export_api_key
set_tracing_export_api_key("sk-...")

# C. Send traces somewhere else
from agents import set_tracing_processor
set_tracing_processor(my_processor)
```

Option B still ships prompt and completion content to OpenAI. Do not enable it for
this project's patient data without an explicit decision — it crosses a data
boundary that the rest of the architecture is careful about.

---

## Known base_url values

| Provider | `base_url` | Notes |
|----------|-----------|-------|
| OpenAI | `None` (omit) | Default; tracing works |
| Groq | `https://api.groq.com/openai/v1` | No `json_schema`; fast, cheap |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | Trailing slash required |
| OpenRouter | `https://openrouter.ai/api/v1` | Model ids namespaced, e.g. `anthropic/claude-3.5-sonnet` |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/v1` | Deployment name is the model id |
| Ollama (local) | `http://localhost:11434/v1` | Any placeholder api_key |
| vLLM / LM Studio | `http://localhost:8000/v1` | Any placeholder api_key |

Providers differ in what they support. Confirm before relying on a feature:
structured outputs (`json_schema`), vision, tool calling, streaming.

---

## LiteLLM — many providers, one interface

For providers without an OpenAI-compatible endpoint (Anthropic, Bedrock, Vertex):

```python
from agents.extensions.models.litellm_model import LitellmModel

model = LitellmModel(model="anthropic/claude-3-5-sonnet", api_key=key)
```

Requires the `litellm` extra. Not used in this repo — `ai_settings` assumes an
OpenAI-compatible `base_url`. Adding it would mean a schema change, so raise it
with the user before introducing it.

---

## Mixing providers in one process

Per-agent models are independent, so two providers can coexist:

```python
openai_agent = Agent(name="OpenAI", model="gpt-4.1")

groq_client = AsyncOpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
groq_agent = Agent(
    name="Groq",
    model=OpenAIChatCompletionsModel(model="llama-3.3-70b-versatile", openai_client=groq_client),
)

a = await Runner.run(openai_agent, "Hello")
b = await Runner.run(groq_agent, "Hello")
```

Caveat: `set_tracing_disabled(True)` and `set_default_openai_api(...)` are
**process-global**. Disabling tracing for the third-party agent also disables it
for the OpenAI one. Use `set_tracing_export_api_key` instead if you need both.

---

## Anti-patterns

| ❌ Don't | Why |
|---------|-----|
| `os.environ["OPENAI_API_KEY"] = gemini_key` | Misroutes SDK auth; produces the misleading 400 |
| Import `AsyncOpenAI` from `openai` in SDK code | Version/type mismatches |
| Skip `set_tracing_disabled` for a non-OpenAI key | 401 in the exporter, cryptic 400 at the call site |
| Build a client per request | Drops connection pooling; construct from settings and reuse |
| Hardcode `base_url` in an agent module | Provider is per-clinic config — read it from `ai_settings` |
| `set_default_openai_client` in a multi-tenant process | One tenant's provider leaks into another's request |
| Log the API key or a decrypted secret | Keys are AES-GCM encrypted at rest; keep them out of logs |
