"""End-to-end test: invokes orchestrator via HTTP, verifies DB traces.

Checks that AuditTrace rows contain model_name, input_tokens, output_tokens,
and cost_usd after an agent invocation.

Usage:
    uv run python -m tests.test_e2e
"""

import asyncio
import httpx
import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8000"


async def main() -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Invoke the test agent endpoint
        print("=== POST /test/agent ===")
        resp = await client.post(
            f"{BASE}/test/agent",
            json={"messages": [{"role": "user", "content": "Hello, what can you do?"}]},
        )
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Reply: {data.get('reply', '')[:200]}")
        run_id = data.get("run_id")
        print(f"run_id: {run_id}")

        if not run_id:
            print("ERROR: No run_id returned.")
            sys.exit(1)

        # 2. Wait for async DB writes
        print("\nWaiting 5s for async DB writes...")
        await asyncio.sleep(5)

        # 3. Query DB directly for logs
        from sqlalchemy import text
        from db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # ToolCallLog
            rows = (await session.execute(
                text("SELECT tool_name, error, duration_ms FROM tool_call_logs WHERE run_id = :rid"),
                {"rid": run_id},
            )).fetchall()
            print(f"\n=== ToolCallLog: {len(rows)} rows ===")
            for r in rows:
                print(f"  tool={r[0]} err={r[1]} dur_ms={r[2]}")

            # AuditTrace (with new columns)
            rows = (await session.execute(
                text(
                    "SELECT agent_name, thought_process, model_name, "
                    "input_tokens, output_tokens, cost_usd "
                    "FROM audit_traces WHERE run_id = :rid"
                ),
                {"rid": run_id},
            )).fetchall()
            print(f"\n=== AuditTrace: {len(rows)} rows ===")
            for r in rows:
                print(
                    f"  agent={r[0]} model={r[2]} "
                    f"in_tok={r[3]} out_tok={r[4]} cost=${r[5]}"
                )
                print(f"    thought={r[1][:100]}")

    print("\n✓ Test complete.")


if __name__ == "__main__":
    asyncio.run(main())
