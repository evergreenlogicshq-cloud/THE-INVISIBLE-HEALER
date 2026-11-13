"""
The Invisible Healer
Phase 04 - Alembic Migration Environment

Responsibilities:
    1. Read existing application configuration.
    2. Connect Alembic to SQLAlchemy metadata.
    3. Run online and offline migrations.
    4. Detect schema changes for managed models.
    5. Avoid autogenerating operations against
       unrelated Supabase tables.
    6. Prevent credential exposure in logs.

Important:
    - Never call Base.metadata.create_all().
    - Never perform migrations on FastAPI startup.
    - Never execute unreviewed destructive changes.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL, make_url

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# ============================================
# ALEMBIC CONFIGURATION
# ============================================

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ============================================
# APPLICATION MODEL METADATA
# ============================================

# Phase 04 contains no domain models yet.
#
# Future phases must import their ORM models
# so SQLAlchemy registers them in Base.metadata.
#
# Example for a later phase:
#
# from app.models import admin_user
#
# Do not import a model before it exists.

target_metadata = Base.metadata


# ============================================
# DATABASE CONFIGURATION
# ============================================


def get_database_url() -> URL:
    """
    Read and validate the application's database URL.
    A URL object avoids manually interpolating
    credentials into configuration strings.

    Psycopg 3 is the project's PostgreSQL driver.
    """

    settings = get_settings()
    database_url = make_url(settings.DATABASE_URL)

    if database_url.drivername == "postgresql":
        database_url = database_url.set(drivername="postgresql+psycopg")

    return database_url


# ============================================
# AUTOGENERATION FILTER
# ============================================


def include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    """
    Restrict schema comparison to application
    tables registered in Base.metadata.

    Supabase may already contain:
        auth tables
        storage tables
        extensions
        application-independent tables

    Alembic must never automatically propose
    dropping unrelated tables.

    Later application tables become eligible
    automatically when imported into metadata.
    """

    if type_ == "table":
        return name in target_metadata.tables

    return True


# ============================================
# OFFLINE MIGRATIONS
# ============================================


def run_migrations_offline() -> None:
    """
    Generate migration SQL without connecting
    to the actual PostgreSQL database.

    Useful for:
        - SQL preview
        - Migration review
        - Deployment planning

    Offline mode generates SQL; it does not
    verify the current database schema.
    """

    database_url = get_database_url()

    context.configure(
        url=database_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_name=include_name,
        transactional_ddl=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================
# ONLINE MIGRATIONS
# ============================================


def run_migrations_online() -> None:
    """
    Connect to PostgreSQL and execute migrations.
    Uses an independent engine instead of the
    FastAPI application's connection pool.

    NullPool avoids holding long-lived migration
    connections or competing with API workers.
    """

    settings = get_settings()
    database_url = get_database_url()

    # ============================================
    # DATABASE-SPECIFIC CONNECTION ARGUMENTS
    # ============================================

    connect_args: dict[str, object] = {}
    if database_url.get_backend_name() == "postgresql":
        # Psycopg 3 accepts connect_timeout.
        connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT
        # Supabase transaction pooler compatibility.
        if database_url.port == 6543 or database_url.query.get("pgbouncer") == "true":
            connect_args["prepare_threshold"] = None

    elif database_url.get_backend_name() == "sqlite":
        # SQLite uses timeout, not connect_timeout.
        # This branch supports isolated migration tests.
        connect_args["timeout"] = settings.DB_CONNECT_TIMEOUT

    else:
        raise ValueError(
            f"Unsupported migration database backend: {database_url.get_backend_name()}"
        )

    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
        pool_pre_ping=True,
        connect_args=connect_args,
        echo=False,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                include_name=include_name,
                transactional_ddl=True,
            )

            with context.begin_transaction():
                context.run_migrations()

    finally:
        connectable.dispose()


# ============================================
# ENTRY POINT
# ============================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
