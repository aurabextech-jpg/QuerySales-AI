from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings

# Note: For Neon Postgres async driver, use postgresql+asyncpg://
# E.g. DATABASE_URL should be postgresql+asyncpg://user:pass@ep-host.region.aws.neon.tech/neondb


def _build_database_url() -> str:
    """Normalise DATABASE_URL for asyncpg, failing loudly if it is unusable.

    An empty URL makes SQLAlchemy silently fall back to the *sync* psycopg2 dialect,
    which surfaces as "The asyncio extension requires an async driver" at cold start —
    on Vercel that reads like a code bug rather than a missing env var. Name the real
    cause instead.
    """
    db_url = settings.DATABASE_URL.strip()
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add the Neon connection string to .env "
            "(locally) or to the Vercel project environment variables, using the "
            "postgresql+asyncpg:// driver."
        )
    if not db_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "DATABASE_URL must use the async driver 'postgresql+asyncpg://'; "
            "got a URL starting with "
            f"'{db_url.split('://', 1)[0]}://'. Alembic swaps it to the sync "
            "driver itself, so keep asyncpg here."
        )
    # asyncpg spells the SSL query parameter 'ssl', not psycopg2's 'sslmode'.
    parsed = urlparse(db_url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Rename psycopg2's sslmode → asyncpg's ssl.
    if "sslmode" in params:
        params["ssl"] = params.pop("sslmode")

    # Drop libpq-only parameters that asyncpg does not recognise.
    # Neon's console sometimes appends channel_binding; asyncpg raises
    # "unexpected keyword argument 'channel_binding'" on connect.
    _LIBPQ_ONLY = {"channel_binding", "gssencmode", "krbsrvname", "gsslib"}
    for key in _LIBPQ_ONLY:
        params.pop(key, None)

    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


engine = create_async_engine(
    _build_database_url(),
    echo=False,
    future=True,
    # ── Serverless / Neon pool hardening ──────────────────────────────
    # Ping the DB before handing out a connection to detect stale ones.
    pool_pre_ping=True,
    # Recycle connections after 270s (Neon closes idle at ~300s).
    pool_recycle=270,
    # Keep the pool tiny — each Vercel lambda is single-concurrency.
    pool_size=2,
    max_overflow=3,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Yield a scoped async session, guaranteed to close after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

