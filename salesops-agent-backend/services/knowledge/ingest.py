"""Knowledge ingestion pipeline (plan §21).

Orchestrates extract → clean → chunk → embed → store, updating
KnowledgeDocument.status at every stage so the UI can show progress.

On failure: status = 'failed', error_message is a user-safe string,
the full exception is logged server-side.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.user_config import resolve_embedding_config
from db.models import KnowledgeChunk, KnowledgeDocument
from services.knowledge.chunk import chunk_text
from services.knowledge.embed import embed_texts
from services.knowledge.extract import extract_text, ExtractionError

logger = logging.getLogger(__name__)


async def ingest_document(
    doc: KnowledgeDocument,
    raw_bytes: bytes,
    db: AsyncSession,
) -> None:
    """Run the full ingestion pipeline for *doc*.

    Updates doc.status at each stage. On failure, sets status='failed'
    and doc.error_message to a user-safe string.
    """
    try:
        # ── Stage 1: Extract ──────────────────────────────────────────
        doc.status = "extracting"
        await db.commit()

        text_content = extract_text(doc.filename, raw_bytes)
        doc.content = text_content

        # ── Stage 2: Chunk ────────────────────────────────────────────
        doc.status = "chunking"
        await db.commit()

        chunks = chunk_text(
            text_content,
            title=doc.title or doc.filename,
            filename=doc.filename,
        )
        logger.info("Document %s: %d chunks created", doc.id, len(chunks))

        # ── Stage 3: Embed ────────────────────────────────────────────
        doc.status = "embedding"
        await db.commit()

        embed_cfg = await resolve_embedding_config(doc.user_id, db)
        chunk_texts = [c.content for c in chunks]
        embeddings = await embed_texts(chunk_texts, embed_cfg)

        # ── Stage 4: Store ────────────────────────────────────────────
        # Delete any existing chunks (re-ingestion case)
        existing = [c for c in doc.chunks]
        for c in existing:
            await db.delete(c)
        await db.flush()

        for chunk, embedding in zip(chunks, embeddings):
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    embedding=embedding,
                    chunk_metadata=chunk.chunk_metadata,
                )
            )

        doc.chunk_count = len(chunks)
        doc.status = "indexed"
        doc.error_message = None
        await db.commit()

        logger.info(
            "Document %s indexed: %d chunks with %d-dim embeddings",
            doc.id, len(chunks), len(embeddings[0]) if embeddings else 0,
        )

    except ExtractionError as exc:
        logger.warning("Extraction failed for doc %s: %s", doc.id, exc)
        doc.status = "failed"
        doc.error_message = str(exc)
        await db.commit()

    except Exception as exc:
        logger.error(
            "Ingestion failed for doc %s: %s", doc.id, exc, exc_info=True
        )
        doc.status = "failed"
        doc.error_message = "An unexpected error occurred during processing. Please try again."
        await db.commit()
