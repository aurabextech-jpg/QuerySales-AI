"""Alembic env.py — configured for Neon Postgres.

Reads DATABASE_URL from the .env file (via core.config) so we never
hardcode credentials in alembic.ini. Uses the synchronous psycopg2
driver for migrations (swaps out asyncpg if present).
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Project imports ──────────────────────────────────────────────────────
from core.config import settings
from db.models import Base  # noqa: F401  — registers all models with Base.metadata

# ── Alembic config object ───────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url from alembic.ini with our env-variable URL.
# Alembic uses a *sync* driver for migrations, so swap asyncpg → psycopg2.
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
config.set_main_option("sqlalchemy.url", db_url)

# Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The MetaData object that Alembic uses for autogenerate diff detection.
target_metadata = Base.metadata


# ── Offline mode (generates SQL script without DB connection) ────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connects to DB and runs DDL) ───────────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Entrypoint ───────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
