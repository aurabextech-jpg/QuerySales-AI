#!/usr/bin/env python3
"""Verify an OpenAI-compatible provider works with the OpenAI Agents SDK.

Runs the smallest possible agent call against a given base_url + model and
reports, step by step, which layer failed. Use this to separate a credential
problem from an SDK-configuration problem before touching application code.

Usage:
    python check_provider.py --base-url https://api.groq.com/openai/v1 \
                             --model llama-3.3-70b-versatile
    python check_provider.py --model gpt-4o-mini            # real OpenAI
    python check_provider.py --base-url ... --model ... --json-test

The API key is read from --api-key, else AGENT_TEST_API_KEY, else OPENAI_API_KEY.
The key is never printed. Costs a handful of tokens per run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_PROVIDER = 2


def _fail(step: str, err: BaseException, hint: str, code: int) -> int:
    print(f"  FAIL  {step}")
    print(f"        {type(err).__name__}: {err}")
    print(f"  HINT  {hint}")
    return code


def _classify(message: str) -> str | None:
    """Map a provider error message to the fix, per references/troubleshooting.md."""
    low = message.lower()
    if "response_format" in low or "json_schema" in low:
        return ("Provider rejects json_schema. Do not use output_type=; "
                "use prompt-instructed JSON + manual parse.")
    if "authorization" in low or "401" in low or "api key" in low:
        return ("Auth failed. If this key is NOT from platform.openai.com, ensure "
                "set_tracing_disabled(True) runs before any agent init, and that "
                "OPENAI_API_KEY is not set to a non-OpenAI key.")
    if "/responses" in low or "not found" in low or "404" in low:
        return ("Endpoint missing. Provider is likely Chat-Completions-only: "
                'call set_default_openai_api("chat_completions").')
    if "model" in low and ("not" in low or "exist" in low):
        return "Model id is not valid for this provider. Check the provider's model list."
    return None


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=None,
                    help="Provider endpoint. Omit for real OpenAI.")
    ap.add_argument("--model", required=True, help="Model id as the provider names it.")
    ap.add_argument("--api-key", default=None,
                    help="Defaults to $AGENT_TEST_API_KEY, then $OPENAI_API_KEY.")
    ap.add_argument("--json-test", action="store_true",
                    help="Also check the provider returns parseable JSON on request.")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("AGENT_TEST_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  FAIL  no API key")
        print("  HINT  Pass --api-key or set AGENT_TEST_API_KEY.")
        return EXIT_CONFIG

    print(f"Provider : {args.base_url or 'https://api.openai.com/v1 (default)'}")
    print(f"Model    : {args.model}")
    print(f"Key      : ...{api_key[-4:]} ({len(api_key)} chars)")
    print()

    # 1. Import ------------------------------------------------------------
    try:
        from agents import (
            Agent, AsyncOpenAI, ModelSettings, OpenAIChatCompletionsModel, Runner,
            set_default_openai_api, set_tracing_disabled,
        )
    except ImportError as e:
        return _fail("import agents", e, "pip install openai-agents", EXIT_CONFIG)
    print("  OK    import agents")

    # 2. Global SDK config -------------------------------------------------
    # Both are process-global and must precede any Agent construction.
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)
    print("  OK    chat_completions API + tracing disabled")

    if os.environ.get("OPENAI_API_KEY") and args.base_url:
        print("  WARN  OPENAI_API_KEY is set while targeting a non-OpenAI base_url.")
        print("        This misroutes SDK auth in real apps — unset it.")

    # 3. Client + model ----------------------------------------------------
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=args.base_url)
        model = OpenAIChatCompletionsModel(model=args.model, openai_client=client)
    except Exception as e:  # noqa: BLE001
        return _fail("build client/model", e, "Check base_url shape (needs scheme, often /v1).",
                     EXIT_CONFIG)
    print("  OK    client + OpenAIChatCompletionsModel")

    # 4. Minimal live call -------------------------------------------------
    agent = Agent(
        name="Probe",
        instructions="Reply with exactly: OK",
        model=model,
        model_settings=ModelSettings(temperature=0, max_tokens=8),
    )
    try:
        result = await Runner.run(agent, "ping", max_turns=1)
    except Exception as e:  # noqa: BLE001
        hint = _classify(str(e)) or "Verify the credential with a direct curl to the endpoint."
        return _fail("live model call", e, hint, EXIT_PROVIDER)

    out = str(result.final_output or "").strip()
    tokens = getattr(result.context_wrapper.usage, "total_tokens", "?")
    print(f"  OK    live call -> {out!r} ({tokens} tokens)")

    # 5. Optional JSON check ----------------------------------------------
    if args.json_test:
        json_agent = Agent(
            name="JSON probe",
            instructions=('Return a JSON object with exactly these keys:\n'
                          '  "status": the string "ok"\n'
                          '  "n": the number 1\n'
                          "No markdown fences, no extra keys."),
            model=model,
            model_settings=ModelSettings(temperature=0, max_tokens=64),
        )
        try:
            jr = await Runner.run(json_agent, "go", max_turns=1)
        except Exception as e:  # noqa: BLE001
            hint = _classify(str(e)) or "Provider failed on the JSON prompt."
            return _fail("json call", e, hint, EXIT_PROVIDER)

        raw = str(jr.final_output or "")
        text = re.sub(r"\n?```$", "", re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())).strip()
        try:
            parsed = json.loads(text)
            print(f"  OK    prompt-instructed JSON parsed -> {parsed}")
        except json.JSONDecodeError:
            print(f"  WARN  JSON did not parse cleanly; raw_head={raw[:120]!r}")
            print("        Harden _extract_json (fence strip + first {...} fallback).")

    print("\nProvider configuration is usable.")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
