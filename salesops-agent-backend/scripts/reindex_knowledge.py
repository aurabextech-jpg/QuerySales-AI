"""Re-embed every knowledge document of one user with their current embedding config.

Needed after changing the embedding model: stored vectors from another model (or
none at all, as with seeded documents) make knowledge search return nothing.

    uv run python -m scripts.reindex_knowledge demo@querysales.demo
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import KnowledgeDocument, User
from db.session import AsyncSessionLocal
from services.knowledge.ingest import ingest_document


async def main(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()
        if user is None:
            print(f"No user with email {email}")
            return 1
        docs = (
            await db.execute(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.user_id == user.id)
                .options(selectinload(KnowledgeDocument.chunks))
            )
        ).scalars().all()
        failed = 0
        for doc in docs:
            if not doc.content:
                print(f"skip  {doc.title or doc.filename}: no stored text")
                continue
            await ingest_document(doc, doc.content.encode("utf-8"), db)
            failed += doc.status != "indexed"
            detail = f"{doc.chunk_count} chunks" if doc.status == "indexed" else doc.error_message
            print(f"{doc.status:8} {doc.title or doc.filename}: {detail}")
        return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
