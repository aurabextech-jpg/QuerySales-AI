"""Per-user settings endpoints (plan §22, §53, §55).

Every endpoint is user-scoped via ``Depends(get_current_user)``.
Secrets are encrypted at rest (AES-256-GCM) and never returned in responses.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from core.crypto import decrypt_secret, encrypt_secret, mask_secret
from core.security import get_current_user
from core.user_config import ConfigurationMissing, resolve_llm_config, resolve_embedding_config
from db.models import (
    User,
    UserEmailConfig,
    UserEmbeddingConfig,
    UserLLMConfig,
)
from db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
#  Pydantic models
# ═════════════════════════════════════════════════════════════════════════════


# ── LLM ────────────────────────────────────────────────────────────────────

class LLMConfigResponse(BaseModel):
    configured: bool
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    api_key_masked: Optional[str] = None


class LLMConfigUpdate(BaseModel):
    provider_name: str = "openai"
    base_url: str
    api_key: Optional[str] = None  # omit to keep existing
    model: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096


class TestResult(BaseModel):
    success: bool
    message: str


# ── Embedding ──────────────────────────────────────────────────────────────

class EmbeddingConfigResponse(BaseModel):
    configured: bool
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    dimension: Optional[int] = None
    api_key_masked: Optional[str] = None


class EmbeddingConfigUpdate(BaseModel):
    provider_name: str = "openai"
    base_url: str
    api_key: Optional[str] = None
    model: str
    dimension: int = 1536


# ── Email ──────────────────────────────────────────────────────────────────

class EmailConfigResponse(BaseModel):
    configured: bool
    provider: Optional[str] = None
    email_address: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    has_password: bool = False


class EmailConfigUpdate(BaseModel):
    provider: str = "gmail_smtp"
    email_address: str
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_password: Optional[str] = None


# ── Database ───────────────────────────────────────────────────────────────

class DatabaseStatus(BaseModel):
    postgres: str
    pgvector: str


# ═════════════════════════════════════════════════════════════════════════════
#  LLM settings
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/llm", response_model=LLMConfigResponse)
async def get_llm_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if not row:
        return LLMConfigResponse(configured=False)
    return LLMConfigResponse(
        configured=True,
        provider_name=row.provider_name,
        base_url=row.base_url,
        model=row.model,
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        api_key_masked=mask_secret(decrypt_secret(row.api_key_encrypted)),
    )


@router.put("/llm", response_model=LLMConfigResponse)
async def put_llm_settings(
    body: LLMConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
    )
    row = result.scalars().first()

    # Encrypt the new key, or keep the existing one if omitted.
    encrypted_key = encrypt_secret(body.api_key) if body.api_key else None

    if row:
        row.provider_name = body.provider_name
        row.base_url = body.base_url
        row.model = body.model
        row.temperature = body.temperature
        row.max_tokens = body.max_tokens
        if encrypted_key is not None:
            row.api_key_encrypted = encrypted_key
    else:
        if not body.api_key:
            raise HTTPException(
                status_code=400,
                detail="api_key is required when creating a new configuration.",
            )
        row = UserLLMConfig(
            user_id=user.id,
            provider_name=body.provider_name,
            base_url=body.base_url,
            api_key_encrypted=encrypted_key or "",
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)

    return LLMConfigResponse(
        configured=True,
        provider_name=row.provider_name,
        base_url=row.base_url,
        model=row.model,
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        api_key_masked=mask_secret(decrypt_secret(row.api_key_encrypted)),
    )


@router.post("/llm/test", response_model=TestResult)
async def test_llm_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cfg = await resolve_llm_config(user.id, db)
    except ConfigurationMissing as exc:
        return TestResult(success=False, message=exc.message)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        resp = await client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": "Say hello in one word."}],
            max_tokens=10,
        )
        answer = resp.choices[0].message.content or ""
        return TestResult(success=True, message=f"Model responded: {answer.strip()}")
    except Exception as exc:
        logger.warning("LLM test failed for user %s: %s", user.id, exc)
        return TestResult(success=False, message=f"Connection failed: {type(exc).__name__}")


@router.delete("/llm")
async def delete_llm_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if row:
        await db.delete(row)
        await db.commit()
    return {"deleted": True}


# ═════════════════════════════════════════════════════════════════════════════
#  Embedding settings
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/embedding", response_model=EmbeddingConfigResponse)
async def get_embedding_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserEmbeddingConfig).where(UserEmbeddingConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if not row:
        return EmbeddingConfigResponse(configured=False)
    return EmbeddingConfigResponse(
        configured=True,
        provider_name=row.provider_name,
        base_url=row.base_url,
        model=row.model,
        dimension=row.dimension,
        api_key_masked=mask_secret(decrypt_secret(row.api_key_encrypted)),
    )


@router.put("/embedding", response_model=EmbeddingConfigResponse)
async def put_embedding_settings(
    body: EmbeddingConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Decision D2: dimension must be 1536.
    if body.dimension != 1536:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Embedding dimension must be 1536 (got {body.dimension}). "
                "The knowledge_chunks column is fixed at vector(1536). "
                "Use a model that outputs 1536 dimensions, or pass "
                "dimensions=1536 to the API."
            ),
        )

    result = await db.execute(
        select(UserEmbeddingConfig).where(UserEmbeddingConfig.user_id == user.id)
    )
    row = result.scalars().first()

    encrypted_key = encrypt_secret(body.api_key) if body.api_key else None

    if row:
        row.provider_name = body.provider_name
        row.base_url = body.base_url
        row.model = body.model
        row.dimension = body.dimension
        if encrypted_key is not None:
            row.api_key_encrypted = encrypted_key
    else:
        if not body.api_key:
            raise HTTPException(
                status_code=400,
                detail="api_key is required when creating a new configuration.",
            )
        row = UserEmbeddingConfig(
            user_id=user.id,
            provider_name=body.provider_name,
            base_url=body.base_url,
            api_key_encrypted=encrypted_key or "",
            model=body.model,
            dimension=body.dimension,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)

    return EmbeddingConfigResponse(
        configured=True,
        provider_name=row.provider_name,
        base_url=row.base_url,
        model=row.model,
        dimension=row.dimension,
        api_key_masked=mask_secret(decrypt_secret(row.api_key_encrypted)),
    )


@router.post("/embedding/test", response_model=TestResult)
async def test_embedding_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cfg = await resolve_embedding_config(user.id, db)
    except ConfigurationMissing as exc:
        return TestResult(success=False, message=exc.message)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        resp = await client.embeddings.create(
            model=cfg.model,
            input=["test"],
        )
        dim = len(resp.data[0].embedding)
        return TestResult(
            success=True,
            message=f"Embedding returned {dim} dimensions.",
        )
    except Exception as exc:
        logger.warning("Embedding test failed for user %s: %s", user.id, exc)
        return TestResult(success=False, message=f"Connection failed: {type(exc).__name__}")


@router.delete("/embedding")
async def delete_embedding_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserEmbeddingConfig).where(UserEmbeddingConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if row:
        await db.delete(row)
        await db.commit()
    return {"deleted": True}


# ═════════════════════════════════════════════════════════════════════════════
#  Email settings
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/email", response_model=EmailConfigResponse)
async def get_email_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserEmailConfig).where(UserEmailConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if not row:
        return EmailConfigResponse(configured=False)
    return EmailConfigResponse(
        configured=True,
        provider=row.provider,
        email_address=row.email_address,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        has_password=bool(row.smtp_password_encrypted),
    )


@router.put("/email", response_model=EmailConfigResponse)
async def put_email_settings(
    body: EmailConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserEmailConfig).where(UserEmailConfig.user_id == user.id)
    )
    row = result.scalars().first()

    encrypted_pw = encrypt_secret(body.smtp_password) if body.smtp_password else None

    if row:
        row.provider = body.provider
        row.email_address = body.email_address
        row.smtp_host = body.smtp_host
        row.smtp_port = body.smtp_port
        if encrypted_pw is not None:
            row.smtp_password_encrypted = encrypted_pw
    else:
        row = UserEmailConfig(
            user_id=user.id,
            provider=body.provider,
            email_address=body.email_address,
            smtp_host=body.smtp_host,
            smtp_port=body.smtp_port,
            smtp_password_encrypted=encrypted_pw,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)

    return EmailConfigResponse(
        configured=True,
        provider=row.provider,
        email_address=row.email_address,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        has_password=bool(row.smtp_password_encrypted),
    )


@router.post("/email/test", response_model=TestResult)
async def test_email_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test SMTP connectivity — connect + authenticate, never send."""
    result = await db.execute(
        select(UserEmailConfig).where(UserEmailConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if not row or not row.smtp_host:
        return TestResult(success=False, message="Email not configured.")

    try:
        import smtplib

        pw = (
            decrypt_secret(row.smtp_password_encrypted)
            if row.smtp_password_encrypted
            else None
        )
        with smtplib.SMTP(row.smtp_host, row.smtp_port or 587, timeout=10) as smtp:
            smtp.starttls()
            if pw:
                smtp.login(row.email_address, pw)
        return TestResult(success=True, message="SMTP connection successful.")
    except Exception as exc:
        logger.warning("SMTP test failed for user %s: %s", user.id, exc)
        return TestResult(success=False, message=f"SMTP failed: {type(exc).__name__}")


@router.delete("/email")
async def delete_email_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserEmailConfig).where(UserEmailConfig.user_id == user.id)
    )
    row = result.scalars().first()
    if row:
        await db.delete(row)
        await db.commit()
    return {"deleted": True}


# ═════════════════════════════════════════════════════════════════════════════
#  Database status (read-only, never exposes DSN)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/database", response_model=DatabaseStatus)
async def get_database_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pg_status = "disconnected"
    pv_status = "unknown"
    try:
        await db.execute(text("SELECT 1"))
        pg_status = "connected"
    except Exception:
        pass

    try:
        r = await db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        row = r.first()
        pv_status = f"enabled ({row[0]})" if row else "not installed"
    except Exception:
        pass

    return DatabaseStatus(postgres=pg_status, pgvector=pv_status)
