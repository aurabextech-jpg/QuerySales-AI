"""Neon Auth (Better Auth) JWT verification for FastAPI.

Verifies JWTs issued by Neon Auth by fetching the JWKS from
the Neon Auth .well-known/jwks.json endpoint and validating
the token signature (EdDSA / Ed25519).

Uses PyJWT + cryptography (not python-jose) because PyJWT
natively supports the EdDSA algorithm that Neon Auth uses.
"""

import logging
from datetime import timedelta

import jwt
from cryptography.fernet import Fernet
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from db.models import User
from db.session import get_db

logger = logging.getLogger(__name__)

# ── Encryption Helpers ───────────────────────────────────────────────────

def get_fernet() -> Fernet:
    """Get Fernet instance using the configured ENCRYPTION_KEY."""
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY must be set in the environment.")
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    """Encrypt a plaintext token."""
    if not token:
        return token
    f = get_fernet()
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token."""
    if not encrypted_token:
        return encrypted_token
    f = get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()


security = HTTPBearer()


# ── JWKS client (caches keys automatically) ─────────────────────────────

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazily initialise and return the JWKS client singleton."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    jwks_url = settings.NEON_AUTH_JWKS_URL
    if not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NEON_AUTH_JWKS_URL is not configured",
        )

    logger.info("Initialising PyJWKClient with JWKS URL: %s", jwks_url)
    _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


# ── Auth dependency ──────────────────────────────────────────────────────

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify the Neon Auth JWT and return the authenticated user.

    On first login the user row is created in our local `users` table
    so that we can attach workflow runs, audit traces, etc.
    """
    credentials = token.credentials
    logger.info("Verifying JWT (first 20 chars): %s...", credentials[:20])

    # ── 1. Resolve signing key from JWKS ─────────────────────────────
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(credentials)
    except PyJWKClientError as exc:
        logger.error("JWKS key resolution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Unexpected JWKS error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable (JWKS failure)",
        )

    # ── 2. Decode and verify the JWT ─────────────────────────────────
    try:
        payload = jwt.decode(
            credentials,
            signing_key.key,
            algorithms=["EdDSA", "ES256", "RS256"],
            options={"verify_aud": False},
            leeway=timedelta(days=7),
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub", "")
    email: str = payload.get("email", "")

    if not user_id:
        logger.warning("Token verified but missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    logger.info("JWT verified for user_id=%s email=%s", user_id, email)

    # ── 3. Upsert user in local DB ───────────────────────────────────
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user:
            logger.info("Creating new user record for %s", email)
            user = User(id=user_id, email=email, role="sales_rep")
            db.add(user)
            await db.commit()
            await db.refresh(user)
    except Exception as db_exc:
        logger.error("Database error during user upsert: %s", db_exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal database error during authentication",
        )

    return user


async def get_sales_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    """Gate access to sales-manager-only endpoints."""
    if current_user.role != "sales_manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions — sales_manager role required",
        )
    return current_user
