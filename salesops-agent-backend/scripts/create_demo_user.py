"""Create the loginable demo user and seed their demo data.

The Phase 6 seed created local-only users (no Neon Auth accounts), so those
users cannot log in through the dashboard. This script creates a real demo
account:

1. Signs the demo user up against Neon Auth (Better Auth). If the account
   already exists, signs in instead — the script is idempotent.
2. Captures the *real* Neon Auth user id. This matters because
   ``core/security.py:get_current_user`` upserts local users by ``id`` (the
   JWT ``sub`` claim), not by email — seeding against a locally generated id
   would leave the demo user with an empty dashboard after login.
3. Seeds the demo dataset (User A: 5 leads + 4 knowledge documents, chunked
   and ready for embedding) for that user id.

Usage:
    python -m scripts.create_demo_user
    python -m scripts.create_demo_user --email demo@querysales.demo --password 'Demo1234!'

Better Auth requires an ``Origin`` header on sign-up (CSRF check); the default
is the local web app URL. Point ``--origin`` at the deployed dashboard when
running against production.

The default credentials are the ones documented in querysales-web/README.md.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import httpx
from sqlalchemy import select

from core.config import settings
from db.models import User
from db.session import AsyncSessionLocal
from scripts.seed_demo import (
    USER_A_DOCS,
    USER_A_LEADS,
    _run_ingestion,
    _seed_documents,
    _seed_leads,
)

logger = logging.getLogger(__name__)

DEFAULT_DEMO_EMAIL = "demo@querysales.demo"
DEFAULT_DEMO_PASSWORD = "Demo1234!"
DEFAULT_DEMO_NAME = "Demo User"
DEFAULT_ORIGIN = "http://localhost:3000"


def _user_id_from(response_data: dict) -> str | None:
    """Pull the user id out of a Better Auth sign-up/sign-in response."""
    user = response_data.get("user") or {}
    user_id = user.get("id")
    return user_id if isinstance(user_id, str) and user_id else None


def sign_up_or_in(email: str, password: str, name: str, origin: str) -> str:
    """Create the Neon Auth account, or sign in if it already exists.

    Returns the Neon Auth user id — the value the JWT ``sub`` claim will
    carry when this user logs in.
    """
    base = settings.NEON_AUTH_URL
    if not base:
        raise RuntimeError("NEON_AUTH_URL is not configured in the backend .env")

    # Better Auth rejects sign-up without an Origin header (MISSING_ORIGIN).
    auth_headers = {"Origin": origin}

    with httpx.Client(timeout=30.0) as client:
        # Sign-up first: on a fresh instance this creates the account.
        try:
            res = client.post(
                f"{base}/sign-up/email",
                json={"email": email, "password": password, "name": name},
                headers=auth_headers,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Could not reach Neon Auth at {base}: {exc}") from exc

        if res.status_code < 400:
            user_id = _user_id_from(res.json())
            if user_id:
                print(f"Created Neon Auth account: {email} (id={user_id})")
                return user_id
            logger.warning("Sign-up succeeded but response had no user id; trying sign-in")

        # A 4xx here usually means the account already exists → verify the
        # password matches so the documented credentials stay truthful.
        try:
            res = client.post(
                f"{base}/sign-in/email",
                json={"email": email, "password": password},
                headers=auth_headers,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Could not reach Neon Auth at {base}: {exc}") from exc

        if res.status_code >= 400:
            raise RuntimeError(
                f"The account {email} already exists in Neon Auth but the password "
                "did not match. Re-run with --password <existing password>, or delete "
                "the account in the Neon console and re-run."
            )

        user_id = _user_id_from(res.json())
        if not user_id:
            raise RuntimeError("Neon Auth sign-in response did not include a user id")

        print(f"Neon Auth account verified: {email} (id={user_id})")
        return user_id


async def _get_or_create_local_user(db, email: str, user_id: str) -> User:
    """Local user row keyed by the Neon Auth id (upserts match on id)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user:
        print(f"Local user row exists: {email} (id={user_id})")
        return user

    # Guard against a stale row seeded with a locally generated id — its
    # dependent rows (leads, docs) would silently belong to the wrong user.
    result = await db.execute(select(User).where(User.email == email))
    stale = result.scalars().first()
    if stale:
        raise RuntimeError(
            f"A local user row for {email} exists with id={stale.id}, which does not "
            f"match the Neon Auth id={user_id}. Delete the stale row and its data, "
            "or pick a different demo email."
        )

    user = User(id=user_id, email=email, role="sales_rep")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print(f"Created local user row: {email} (id={user_id})")
    return user


async def create_demo_user(email: str, password: str, name: str, origin: str) -> None:
    """Sign up in Neon Auth, then seed the demo dataset for that user id."""
    user_id = sign_up_or_in(email, password, name, origin)

    async with AsyncSessionLocal() as db:
        user = await _get_or_create_local_user(db, email, user_id)

        leads_created = await _seed_leads(db, user, USER_A_LEADS)
        print(f"Leads created: {leads_created} (dataset defines {len(USER_A_LEADS)})")

        docs = await _seed_documents(db, user, USER_A_DOCS)
        print(f"Documents created: {len(docs)} (dataset defines {len(USER_A_DOCS)})")

        if docs:
            chunked = await _run_ingestion(db, docs)
            print(f"Documents chunked: {chunked}")

    print()
    print("=" * 60)
    print("Demo user ready. Log in at the web dashboard with:")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print("  Dataset:  5 leads, 4 knowledge documents (chunked)")
    print()
    print("For live agent analysis, configure LLM + Embedding keys in")
    print("Settings, then process the knowledge documents to embed them.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the demo user in Neon Auth and seed their demo data"
    )
    parser.add_argument("--email", default=DEFAULT_DEMO_EMAIL, help="Demo user email")
    parser.add_argument("--password", default=DEFAULT_DEMO_PASSWORD, help="Demo user password")
    parser.add_argument("--name", default=DEFAULT_DEMO_NAME, help="Demo user display name")
    parser.add_argument(
        "--origin",
        default=DEFAULT_ORIGIN,
        help="Web app origin for Better Auth's CSRF check (default: localhost:3000)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(create_demo_user(args.email, args.password, args.name, args.origin))


if __name__ == "__main__":
    main()
