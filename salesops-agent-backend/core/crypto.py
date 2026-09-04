"""AES-256-GCM credential encryption (Decision D3, plan §45-46).

The key comes from ``settings.ENCRYPTION_KEY`` — a url-safe base64-encoded
32-byte value (44 characters including padding).  The *same* key also serves
the legacy Fernet path in ``core/security.py`` because a Fernet key is
url-safe-base64(32 bytes) (Decision D7).

A fresh random 12-byte nonce is generated for every encryption, so two
encryptions of the same plaintext always produce different ciphertext.

Stored format: ``base64(nonce || ciphertext || tag)``  (the AESGCM class
appends the 16-byte tag automatically).
"""

from __future__ import annotations

import base64
import os
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import settings

logger = logging.getLogger(__name__)

# ── Key initialisation ──────────────────────────────────────────────────────
# Fail loudly at import if the key is malformed.  A silent fallback to
# plaintext storage would be a security bug.

_KEY_BYTES: bytes = b""


def _load_key() -> bytes:
    """Decode ENCRYPTION_KEY from base64 and validate length."""
    raw = settings.ENCRYPTION_KEY.strip()
    if not raw:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Add it to .env (locally) or to the "
            "Vercel project environment variables. Generate with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        key_bytes = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        raise RuntimeError(
            f"ENCRYPTION_KEY is not valid base64: {exc}"
        ) from exc
    if len(key_bytes) != 32:
        raise RuntimeError(
            f"ENCRYPTION_KEY must decode to exactly 32 bytes (got {len(key_bytes)}). "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return key_bytes


try:
    _KEY_BYTES = _load_key()
    _aesgcm = AESGCM(_KEY_BYTES)
except RuntimeError:
    # Allow import to succeed when no .env is loaded (e.g. during collect-static
    # or type-checking), but encrypt/decrypt will fail at call time.
    _aesgcm = None  # type: ignore[assignment]
    logger.warning("ENCRYPTION_KEY not available — crypto disabled until set")


def _get_aesgcm() -> AESGCM:
    if _aesgcm is None:
        raise RuntimeError(
            "ENCRYPTION_KEY is not configured. Cannot encrypt/decrypt credentials."
        )
    return _aesgcm


# ── Public API ──────────────────────────────────────────────────────────────


def encrypt_secret(plaintext: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM and return a base64 blob.

    Format: ``base64(nonce(12) || ciphertext || tag(16))``
    """
    if not plaintext:
        return ""
    nonce = os.urandom(12)
    ct = _get_aesgcm().encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt_secret(blob: str) -> str:
    """Decrypt a blob produced by :func:`encrypt_secret`."""
    if not blob:
        return ""
    raw = base64.urlsafe_b64decode(blob)
    if len(raw) < 28:  # 12 nonce + 16 tag minimum
        raise ValueError("Ciphertext blob is too short to be valid")
    nonce, ct = raw[:12], raw[12:]
    return _get_aesgcm().decrypt(nonce, ct, None).decode("utf-8")


def mask_secret(plaintext: str) -> str:
    """Return a human-safe mask like ``sk-••••1234``.

    Shows up to 4 leading + 4 trailing characters when the secret is long
    enough; otherwise returns a fixed mask.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "••••"
    return f"{plaintext[:4]}••••{plaintext[-4:]}"
