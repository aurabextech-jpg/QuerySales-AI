import asyncio
import logging
import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db

from agent_core.orchestrator import run_orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    prompt = "Find me 2 software companies in Lahore and tell me their names."
    messages = [{"role": "user", "content": prompt}]
    run_id = str(uuid.uuid4())
    
    # Get a DB session
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        print(f"Running orchestrator with prompt: '{prompt}'")
        result = await run_orchestrator(messages, run_id=run_id, db=db)
        print("\n--- FINAL RESULT ---")
        print(result)
        print("--------------------")
    finally:
        await db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
