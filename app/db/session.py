"""
The Invisible Healer
Database Engine and Session Management

Phase 03 - SQLAlchemy Database Connection

Responsibilities:
    1. Create a SQLAlchemy engine.
    2. Configure PostgreSQL connection pooling.
    3. Create isolated database session factories.
    4. Provide request-scoped sessions.
    5. Commit successful transactions.
    6. Roll back failed transactions.
    7. Verify database connectivity.
    8. Dispose owned connection pools at shutdown.

Architecture:
    FastAPI
        |
        v
    Database Dependency
        |
        v
    SQLAlchemy Session
        |
        v
    SQLAlchemy Engine
        |
        v
    Psycopg 3
        |
        v
    Supabase PostgreSQL

Important:
    - Never log DATABASE_URL.
    - Never create tables automatically.
    - Never share a Session between requests.
    - Never share a Session across concurrent tasks.
    - Database network access is synchronous.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)


# ============================================
# DATABASE ENGINE FACTORY
# ============================================


def create_database_engine(settings: Settings) -> Engine:
    """
    Create the SQLAlchemy database engine.
    Engine creation configures the connection pool.
    It does not immediately establish a connection.
    Connections are created when an operation
    first checks out a database connection.
    The engine is intended to be application-scoped.
    """

    # Disable server-side prepared statements for
    # compatibility with transaction-mode pooling.
    #
    # Psycopg's normal prepared statement behavior
    # remains in place for other connection modes.

    connect_args = {"connect_timeout": settings.DB_CONNECT_TIMEOUT}
    from sqlalchemy.engine import make_url

    database_url = make_url(settings.DATABASE_URL)

    if database_url.port == 6543 or database_url.query.get("pgbouncer") == "true":
        connect_args["prepare_threshold"] = None

    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=(settings.DB_ECHO and not settings.is_production),
        connect_args=connect_args,
        future=True,
    )

    logger.info("SQLAlchemy database engine configured.")

    return engine


# ============================================
# DATABASE SESSION FACTORY
# ============================================


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """
    Create a session factory bound to an engine.
    Each invocation of the resulting factory
    returns a separate SQLAlchemy Session.
    Sessions must not be shared between requests.
    """

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
        autocommit=False,
    )


# ============================================
# DATABASE CONNECTIVITY
# ============================================


def check_database_connection(engine: Engine) -> bool:
    """
    Verify database connectivity.
    Executes a minimal PostgreSQL-compatible
    SELECT 1 statement.
    A failed connection raises SQLAlchemyError
    or an underlying driver exception.
    The caller decides how to report failure.
    The SQL statement is infrastructure-only,
    not application business logic.
    """

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        return result.scalar_one() == 1


# ============================================
# DATABASE SESSION DEPENDENCY
# ============================================


def get_db(request: Request) -> Generator[Session, None, None]:
    """
    Supply one database Session per request.
    The FastAPI application owns the engine
    and session factory.

    Transaction policy:
        - Successful dependency execution commits.
        - Exceptions cause a rollback.
        - The Session always closes.

    Important:
        For data-writing endpoints, services should
        flush changes when needed and let the
        transaction owner commit.
        For operations requiring explicit commit
        guarantees before building a response,
        use an explicit transaction boundary in
        the service or endpoint.

        Do not call commit() in every repository.
    """

    session_factory = request.app.state.db_session_factory

    with session_factory() as session:
        try:
            yield session

            session.commit()

        except Exception:
            session.rollback()
            raise


# ============================================
# REUSABLE TRANSACTION CONTEXT
# ============================================


@contextmanager
def database_transaction(
    session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    """
    Create a transaction outside an HTTP request.

    Intended for future:
        - Admin jobs
        - Database-backed workers
        - Maintenance commands
        - Data import services

    Successful execution commits.
    Exceptions trigger rollback.
    """

    with session_factory() as session, session.begin():
        yield session


# ============================================
# TYPED FASTAPI DEPENDENCY
# ============================================

DatabaseSession = Annotated[Session, Depends(get_db)]
