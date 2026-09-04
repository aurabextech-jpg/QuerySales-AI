"""Knowledge document management endpoints (plan §28).

Upload, list, process (ingest), delete, and search knowledge documents.
All user-scoped.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.security import get_current_user
from core.user_config import resolve_embedding_config, ConfigurationMissing
from db.models import KnowledgeChunk, KnowledgeDocument, User
from db.session import get_db
from services.knowledge.extract import ExtractionError, validate_file
from services.knowledge.ingest import ingest_document
from services.knowledge.search import search_knowledge

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    id: str
    filename: str
    title: Optional[str] = None
    file_type: str
    status: str
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: str
    content: str
    chunk_index: int
    document_title: Optional[str] = None
    document_filename: str
    similarity: float
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchHit]
    total: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == user.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            title=d.title,
            file_type=d.file_type,
            status=d.status,
            chunk_count=d.chunk_count or 0,
            error_message=d.error_message,
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in docs
    ]


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document. Validates extension and size, stores, then ingests inline."""
    raw = await file.read()

    # Validate before storing
    try:
        validate_file(file.filename or "unknown", len(raw))
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from pathlib import Path

    ext = Path(file.filename or "").suffix.lower()

    doc = KnowledgeDocument(
        user_id=user.id,
        filename=file.filename or "unknown",
        title=file.filename or "unknown",
        file_type=ext,
        status="uploaded",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Ingest inline (extract → chunk → embed → store)
    await ingest_document(doc, raw, db)
    await db.refresh(doc)

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        file_type=doc.file_type,
        status=doc.status,
        chunk_count=doc.chunk_count or 0,
        error_message=doc.error_message,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.post("/{doc_id}/process", response_model=DocumentResponse)
async def reprocess_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-process a document (e.g. after embedding config changed)."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == user.id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.content:
        raise HTTPException(
            status_code=400,
            detail="Document has no extracted content. Re-upload the file.",
        )

    await ingest_document(doc, doc.content.encode("utf-8"), db)
    await db.refresh(doc)

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        file_type=doc.file_type,
        status=doc.status,
        chunk_count=doc.chunk_count or 0,
        error_message=doc.error_message,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks (CASCADE)."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.user_id == user.id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    await db.delete(doc)
    await db.commit()
    return {"deleted": True}


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across the user's knowledge chunks."""
    # Embed the query first
    try:
        embed_cfg = await resolve_embedding_config(user.id, db)
    except ConfigurationMissing as exc:
        raise HTTPException(status_code=400, detail=exc.message)

    from services.knowledge.embed import embed_texts

    query_embeddings = await embed_texts([body.query], embed_cfg)
    query_vec = query_embeddings[0]

    results = await search_knowledge(
        query_embedding=query_vec,
        user_id=user.id,
        db=db,
        top_k=body.top_k,
    )

    return SearchResponse(
        results=[
            SearchHit(
                chunk_id=r.chunk_id,
                content=r.content,
                chunk_index=r.chunk_index,
                document_title=r.document_title,
                document_filename=r.document_filename,
                similarity=r.similarity,
                metadata=r.chunk_metadata,
            )
            for r in results
        ],
        total=len(results),
    )
