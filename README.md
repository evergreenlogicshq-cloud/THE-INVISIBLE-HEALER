
# The Invisible Healer

A modular FastAPI backend for a data-first,
clinically governed AI medical assistant.

## Architecture

- Python FastAPI modular monolith
- Pydantic v2 settings
- REST API routing
- Centralized exception handling
- Application factory and lifespan
- Automated testing with Pytest

## Current implementation

Phase 01 - Project Skeleton and Architecture Boundaries

### Implemented

- Application configuration
- API router
- Health liveness endpoint
- Health readiness endpoint
- Centralized exception handling
- Shared API dependencies
- Configuration validation
- API and configuration tests

### Not yet implemented

- Supabase PostgreSQL integration
- SQLAlchemy ORM
- Alembic migrations
- Admin authentication
- Clinical knowledge database
- LangChain / LangGraph
- AI engines
- Patient chat features

These features belong to subsequent phases.

## Requirements

Python 3.12 or a compatible Python 3.13 release.

## Installation

Create a virtual environment:

    py -3.12 -m venv .venv

Activate:

    .\.venv\Scripts\Activate.ps1

Install dependencies:

    pip install -r requirements-dev.txt

Create local environment configuration:

    Copy-Item .env.example .env

## Start server

    python -m uvicorn app.main:app --reload

## Health endpoints

    GET /health/live
    GET /health/ready

## API documentation

    http://127.0.0.1:8000/docs

## Run tests

    python -m pytest -v

## Architecture rules

1. No src/ directory.
2. App modules live directly under app/.
3. API handlers do not contain database queries.
4. Business logic belongs in services/domain.
5. Persistence belongs in repositories.
6. SQLAlchemy models belong in models.
7. Request/response contracts belong in schemas.
8. AI capabilities belong in engines.
9. LangGraph workflows belong in orchestration.
10. No unreviewed clinical behavior is patient-facing.

## Clinical safety

This project is not approved for patient-facing clinical use
in its current implementation state.

Qualified clinical review and appropriate deployment
authorization are required before release.
