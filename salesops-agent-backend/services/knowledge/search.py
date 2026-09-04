"""Vector similarity search for knowledge retrieval (plan §10, §50).

The user_id filter is INSIDE the SQL query — never applied afterwards.
This is non-negotiable (AGENTS.md §3.2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Must match the column dimension (Decision D2)
EXPECTED_DIMENSION = 1536


@dataclass
class SearchResult:
    chunk_id: str
    content: str
    chunk_index: int
    chunk_metadata: dict
    document_title: str | None
    document_filename: str
    similarity: float


async def search_knowledge(
    query_embedding: list[float],
    user_id: str,
    db: AsyncSession,
    *,
    top_k: int = 5,
) -> list[SearchResult]:
    """Find the top-k most similar chunks for *user_id*.

    The user_id filter is inside the SQL — a different user_id returns zero
    results even if the vectors are identical (plan §50).
    """
    if len(query_embedding) != EXPECTED_DIMENSION:
        raise ValueError(
            f"Query embedding must be {EXPECTED_DIMENSION}-dimensional, "
            f"got {len(query_embedding)}."
        )

    sql = text("""
        SELECT c.id, c.content, c.chunk_index, c.chunk_metadata,
               d.title, d.filename,
               1 - (c.embedding <=> :query_embedding) AS similarity
          FROM knowledge_chunks c
          JOIN knowledge_documents d ON d.id = c.document_id
         WHERE c.user_id = :user_id
           AND c.embedding IS NOT NULL
         ORDER BY c.embedding <=> :query_embedding
         LIMIT :top_k
    """)

    # pgvector expects the vector as a string literal like '[0.1, 0.2, ...]'
    vec_str = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

    result = await db.execute(
        sql,
        {"query_embedding": vec_str, "user_id": user_id, "top_k": top_k},
    )

    results = []
    for row in result.fetchall():
        results.append(
            SearchResult(
                chunk_id=row[0],
                content=row[1],
                chunk_index=row[2],
                chunk_metadata=row[3] or {},
                document_title=row[4],
                document_filename=row[5],
                similarity=float(row[6]) if row[6] is not None else 0.0,
            )
        )

    return results
