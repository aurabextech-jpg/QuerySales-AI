# Structured Output

Getting reliable JSON out of an agent when the provider does not support
`json_schema` response formats.

---

## Why not `output_type=`

`output_type=MyModel` makes the SDK send `response_format: {type: "json_schema", ...}`.
Groq and several other OpenAI-compatible providers accept only `text` and
`json_object`, and reject the request:

```text
BadRequestError: 400 - {'error': {'message': "'response_format.type' : value is
not one of the allowed values ['text','json_object']", 'type': 'invalid_request_error'}}
```

Every agent in `agent-service/` therefore uses **prompt-instructed JSON + manual
parse**. Do not re-add `output_type` unless the target is an OpenAI model
confirmed to support json_schema *and* the provider is pinned — which per-clinic
`ai_settings` cannot guarantee.

---

## The four-part contract

### 1. Instructions spell out the schema

```python
INSTRUCTIONS = (
    "You summarize a dental clinic phone call from its transcript. "
    "Use only what is in the transcript — do not invent details.\n\n"
    "Return a JSON object with exactly these keys:\n"
    '  "summary": string (1-3 concise sentences)\n'
    '  "outcome": one of "booked", "inquired", "abandoned", "other"\n'
    '  "sentiment": one of "positive", "neutral", "negative"\n'
    '  "key_topics": array of up to 5 short strings\n'
    '  "follow_up_required": boolean\n'
    "No markdown fences, no extra keys."
)
```

Enumerate allowed values inline. Always close with the no-fences line — it
measurably reduces fenced output.

### 2. Extract, tolerating fences and prose

```python
def _extract_json(text: str) -> dict:
    """Strip optional markdown fences / surrounding prose, then parse JSON."""
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the first {...} block the model emitted.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
```

### 3. Normalize every field

The model *will* eventually return an out-of-range enum or a missing key. Coerce
rather than raise — a degraded summary beats a 500.

```python
_VALID_OUTCOMES = {"booked", "inquired", "abandoned", "other"}

outcome = parsed.get("outcome", "other")
if outcome not in _VALID_OUTCOMES:
    outcome = "other"
```

For labels that arrive with punctuation or casing drift, strip to letters first:

```python
def _label_of(raw: str) -> str:
    return re.sub(r"[^a-z]", "", (raw or "").lower())
```

### 4. Validate into Pydantic

The normalized dict, never the raw one, goes into the model. Pydantic is the last
gate, not the parser.

---

## Semantic override rules

Classification and generation can disagree inside a single response. Prefer the
observable artifact over the self-reported label.

The email agent's **"body-presence wins"** rule: if the model wrote a reply body,
treat the message as `query` regardless of the label it emitted. It is more
reliable to trust what the model *did* than what it *said it did*.

---

## Vision input

Pass images as `input_image` content parts. A plain string when there are no
images keeps the common path cheap:

```python
def _user_input(email_text: str, attachments: list[ImageAttachment]):
    if not attachments:
        return email_text
    content: list[dict] = [{"type": "input_text", "text": email_text}]
    for att in attachments:
        data_url = f"data:{att.content_type};base64,{att.data_base64}"
        content.append({"type": "input_image", "detail": "auto", "image_url": data_url})
    return [{"role": "user", "content": content}]
```

The chat-completions model converts these to the provider's native `image_url`
parts. Cap what you send — the email path allows 3 images, 1.5 MB each, 3 MB total.

### Vision fallback

Not every configured model supports vision, and `ai_settings` cannot promise it.
Catch the failure and retry text-only, telling the model what it is missing:

```python
try:
    result = await _run(email_text, use_images=bool(attachments))
except Exception:  # noqa: BLE001 — vision unsupported / payload rejected
    if not attachments:
        raise
    logger.warning("vision call failed (%d image(s)); retrying text-only", len(attachments))
    names = ", ".join(a.filename for a in attachments) or "image"
    note = (
        f"{email_text}\n\n[The sender attached {len(attachments)} image file(s): "
        f"{names}. You cannot view them here; acknowledge the attachment(s) and "
        f"offer to review them if relevant.]"
    )
    result = await _run(note, use_images=False)
```

Re-raise when there were no images — that failure is a real error, not a vision
capability gap.

---

## Token accounting

```python
result = await Runner.run(agent, user_input, max_turns=1)
usage = result.context_wrapper.usage
logger.info("summarized call %s | tokens=%s", call_id, usage.total_tokens)
```

Return `total_tokens` alongside the parsed data so callers can log cost per
operation. Log the count — never the prompt or completion text.

---

## Cost discipline

Mandatory on every agent in this repo:

| Control | Implementation |
|---------|----------------|
| Zero-token pre-filter | `heuristics.py` rejects spam/promo before any LLM call |
| Single call | `max_turns=1` — classify and draft in one call, not two |
| Output cap | `ModelSettings(max_tokens=...)`; 400 summaries / 900 email / 400 social |
| Input cap | Truncate transcript, email body, and knowledge to documented limits |
| Kill switch | `ai_settings.enabled` checked in the route before the model is built |
| Idempotence | DB upserts on a unique key so retries never duplicate rows |

Combining classify and draft into one call is deliberate: it halves cost **and**
removes the possibility of a label that disagrees with the generated body.

---

## Debugging bad output

When a field comes back empty or wrong, log a bounded head of the raw output —
enough to distinguish a genuine decision from a formatting slip, short enough not
to dump patient content into logs:

```python
if not reply.body_text:
    logger.info("triage no-reply label=%s images=%d raw_head=%r",
                label, len(attachments), raw[:200])
```
