"""
The Invisible Healer
Database Session Unit Tests

Phase 03 - SQLAlchemy Database Infrastructure

Covers:
    - Engine connectivity
    - Session factory creation
    - Database session dependency
    - Successful transaction commit
    - Transaction rollback
    - Session isolation
    - Request-scoped transaction rollback
    - Context manager cleanup

Testing Strategy:
    SQLite is used only for isolated unit tests.

    The production application uses:
        - SQLAlchemy 2.x
        - Psycopg 3
        - Supabase PostgreSQL

Important:
    - No production tables are created.
    - No external database connection is required.
    - Tests must remain isolated and repeatable.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import (
    Column,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.orm import Session

from app.db.session import (
    DatabaseSession,
    check_database_connection,
    create_session_factory,
    database_transaction,
)

# ============================================
# TEST TABLE FACTORY
# ============================================


def create_test_table(engine: Engine) -> Table:
    """
    Create a disposable test-only database table.

    Purpose:
        Provide a simple table for testing
        successful commits and transaction
        rollbacks.

    Important:
        This table is not part of the
        application's declarative metadata.

        It is not a production ORM model.

        It has no effect on Supabase PostgreSQL.

    Args:
        engine:
            Isolated SQLAlchemy test engine.

    Returns:
        SQLAlchemy Table object.
    """

    metadata = MetaData()

    test_records = Table(
        "test_records",
        metadata,
        Column(
            "id",
            Integer,
            primary_key=True,
        ),
        Column(
            "name",
            String(100),
            nullable=False,
        ),
    )

    metadata.create_all(engine)

    return test_records


# ============================================
# TEST 01 - DATABASE CONNECTION
# ============================================


def test_database_connection(test_engine: Engine) -> None:
    """
    Verify that the SQLAlchemy engine
    can successfully execute a database query.

    Expected:
        check_database_connection() returns True.
    """

    result = check_database_connection(test_engine)
    assert result is True


# ============================================
# TEST 02 - SESSION FACTORY
# ============================================


def test_session_factory(test_engine: Engine) -> None:
    """
    Verify that the session factory
    creates a valid SQLAlchemy Session.

    Expected:
        The created object is a Session.

    The context manager must close the
    session after execution.
    """

    session_factory = create_session_factory(test_engine)

    with session_factory() as session:
        assert isinstance(session, Session)


# ============================================
# TEST 03 - SESSION ISOLATION
# ============================================


def test_session_isolation(test_engine: Engine) -> None:
    """
    Verify that separate calls to the
    session factory create different
    Session instances.

    This is important for preventing
    shared request-level session state.

    Expected:
        first is not second.
    """

    session_factory = create_session_factory(test_engine)

    with (
        session_factory() as first,
        session_factory() as second,
    ):
        assert first is not second


# ============================================
# TEST 04 - TRANSACTION COMMIT
# ============================================


def test_transaction_commit(test_engine: Engine) -> None:
    """
    Verify successful transaction commit.

    Procedure:
        1. Create an isolated test table.
        2. Create a session factory.
        3. Start a managed transaction.
        4. Insert a record.
        5. Exit the transaction normally.
        6. Open another session.
        7. Verify the record was committed.

    Expected:
        The inserted record is persisted.
    """

    table = create_test_table(test_engine)
    factory = create_session_factory(test_engine)
    # ----------------------------------------
    # Insert record inside managed transaction
    # ----------------------------------------

    with database_transaction(factory) as session:
        session.execute(insert(table).values(name="Commit Test"))

    # ----------------------------------------
    # Verify committed data in another session
    # ----------------------------------------

    with factory() as session:
        result = session.execute(select(table.c.name)).scalar_one()

    assert result == "Commit Test"


# ============================================
# TEST 05 - TRANSACTION ROLLBACK
# ============================================


def test_transaction_rollback(test_engine: Engine) -> None:
    """
    Verify automatic rollback when
    an exception occurs inside a transaction.

    Procedure:
        1. Create a test table.
        2. Start a managed transaction.
        3. Insert a record.
        4. Simulate a service failure.
        5. Verify the exception propagates.
        6. Confirm the record was not committed.

    Expected:
        No database records remain.
    """

    table = create_test_table(test_engine)
    factory = create_session_factory(test_engine)

    # ----------------------------------------
    # Simulate failure during transaction
    # ----------------------------------------

    with (
        pytest.raises(ValueError),
        database_transaction(factory) as session,
    ):
        session.execute(insert(table).values(name="Rollback Test"))

        raise ValueError("Simulated service failure")

    # ----------------------------------------
    # Verify rollback
    # ----------------------------------------

    with factory() as session:
        records = session.execute(select(table.c.name)).all()

    assert records == []


# ============================================
# TEST 06 - FASTAPI DATABASE DEPENDENCY
# ============================================


def test_fastapi_database_dependency(client: TestClient, app: FastAPI) -> None:
    """
    Verify SQLAlchemy Session injection
    through FastAPI's dependency system.

    Procedure:
        1. Register an isolated test endpoint.
        2. Request the DatabaseSession dependency.
        3. Execute a SELECT 1 query.
        4. Call the endpoint through TestClient.
        5. Verify the returned result.

    Expected:
        HTTP 200 with a valid database result.

    Important:
        DatabaseSession is an Annotated type
        that already contains Depends(get_db).

        Using it avoids Ruff B008 warnings.
    """

    # ----------------------------------------
    # Temporary test-only endpoint
    # ----------------------------------------

    @app.get("/test/database-dependency")
    def test_route(db: DatabaseSession) -> dict[str, str | int]:
        """
        Execute a minimal database query
        using the injected SQLAlchemy Session.
        """

        result = db.execute(select(1)).scalar_one()

        return {"database": "connected", "result": result}

    # ----------------------------------------
    # Execute API request
    # ----------------------------------------
    response = client.get("/test/database-dependency")
    # ----------------------------------------
    # Verify response
    # ----------------------------------------
    assert response.status_code == 200
    assert response.json() == {"database": "connected", "result": 1}


# ============================================
# TEST 07 - REQUEST TRANSACTION ROLLBACK
# ============================================


def test_dependency_rollback_on_failure(
    client: TestClient, app: FastAPI, test_engine: Engine
) -> None:
    """
    Verify that a failed FastAPI request
    automatically rolls back database changes.

    Procedure:
        1. Create an isolated test table.
        2. Register a temporary POST endpoint.
        3. Inject a request-scoped database Session.
        4. Insert a database record.
        5. Raise a simulated application error.
        6. Verify the exception propagates.
        7. Confirm the record was rolled back.

    Expected:
        The database contains no inserted records.

    Important:
        This tests transaction ownership
        implemented in app/db/session.py.
    """

    table = create_test_table(test_engine)

    # ----------------------------------------
    # Temporary test-only endpoint
    # ----------------------------------------

    @app.post("/test/failing-transaction")
    def failing_route(db: DatabaseSession) -> None:
        """
        Simulate an application failure
        after modifying the database.
        """

        db.execute(insert(table).values(name="Should Roll Back"))

        raise ValueError("Simulated request failure")

    # ----------------------------------------
    # Verify exception propagation
    # ----------------------------------------
    with pytest.raises(ValueError):
        client.post("/test/failing-transaction")
    # ----------------------------------------
    # Verify database rollback
    # ----------------------------------------
    factory = create_session_factory(test_engine)

    with factory() as session:
        records = session.execute(select(table.c.name)).all()

    assert records == []
