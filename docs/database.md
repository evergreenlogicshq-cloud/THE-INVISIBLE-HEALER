
# The Invisible Healer
## Phase 03 — Database Infrastructure

### 1. Overview

The Invisible Healer uses SQLAlchemy 2.x
with Psycopg 3 to connect to Supabase
PostgreSQL.

PostgreSQL is the application's system
of record.

The application uses a modular monolith
architecture.

### 2. Database Components

The database infrastructure consists of:

- app/db/base.py
- app/db/session.py
- app/api/dependencies.py
- app/api/routes/health.py

The application engine is initialized
through the FastAPI lifespan mechanism.

### 3. Connection Configuration

The connection URL must be configured
through DATABASE_URL.

Required format:

postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB

For Supabase, obtain the exact connection
information from the project dashboard.

Use TLS as appropriate for the chosen
Supabase connection method.

Do not store real passwords in documentation.

### 4. Connection Pool

The pool is controlled through:

- DB_POOL_SIZE
- DB_MAX_OVERFLOW
- DB_POOL_TIMEOUT
- DB_POOL_RECYCLE
- DB_CONNECT_TIMEOUT

SQLAlchemy pool_pre_ping is enabled.

The configured pool limits apply per
SQLAlchemy Engine, normally per worker process.

Production pool configuration must be sized
for the database's actual connection limits
and the application's worker count.

### 5. Database Sessions

Each database-using request receives a
separate SQLAlchemy Session.

Sessions are never global shared objects.

A transaction should be committed only after
the required application operation succeeds.

Failed operations must roll back.

Repositories should not independently commit
multi-step application transactions.

For critical writes, transaction completion
must occur before the application reports
success to the client.

### 6. Connectivity Checks

GET /health/live

Checks application liveness only.

GET /health/ready

Checks:
- Application configuration
- Database engine availability
- Real PostgreSQL connectivity

If the required database is unavailable,
readiness returns HTTP 503.

Liveness remains independent of the database.

### 7. Security Requirements

Never:

- Commit .env files
- Log database passwords
- Expose service-role credentials
- Return raw PostgreSQL exceptions
- Embed secrets in browser code
- Share SQLAlchemy Sessions across requests
- Execute LLM-generated SQL
- Enable verbose SQL logging with patient data

### 8. Database Schema Ownership

SQLAlchemy models define application tables.

Alembic owns schema migrations.

Do not invoke Base.metadata.create_all()
during application startup.

Do not modify existing Supabase schemas
without a reviewed migration.

### 9. Testing

Unit and API tests use an isolated
in-memory SQLite fixture.

Database integration tests use a dedicated
PostgreSQL testing database.

To execute ordinary tests:

python -m pytest -q

To run real PostgreSQL integration tests,
set:

RUN_DB_INTEGRATION_TESTS=true

and configure:

TEST_DATABASE_URL

Never run destructive integration tests
against a production clinical database.

### 10. Phase Boundaries

Phase 03 includes:
- Engine creation
- Connection pooling
- Session management
- Database readiness
- Transaction support
- Connectivity testing

Phase 04 introduces:
- Alembic
- Migration configuration
- Database revision tracking
- Model metadata integration
- Migration policies

No clinical application tables are created
in Phase 03.
