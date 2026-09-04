import asyncio
import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_core.orchestrator import run_orchestrator

async def test_agent():
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Keep your response very brief."},
        {"role": "user", "content": "What is the capital of France?"}
    ]
    try:
        print("Running orchestrator...")
        reply = await run_orchestrator(messages)
        print("Reply:", reply)
    except Exception as e:
        print("Error during orchestration:", e)

if __name__ == "__main__":
    asyncio.run(test_agent())
