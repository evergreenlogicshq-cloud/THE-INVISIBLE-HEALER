"""
The Invisible Healer
SQLAlchemy Declarative Base

Phase 03 - Database Infrastructure

Purpose:
    Provide a centralized declarative base
    for all future SQLAlchemy ORM models.

Future phases:
    Phase 04 - Alembic migration baseline
    Phase 06 - Admin identity models
    Phase 09 - Medical concepts
    Phase 10 - Health issues and symptoms

Important:
    This module does not create database tables.
    Database schema changes are managed
    through Alembic migrations.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# --------------------------------------------
# Naming conventions for database constraints
# --------------------------------------------

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": ("fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"),
    "pk": "pk_%(table_name)s",
}


# --------------------------------------------
# Central metadata
# --------------------------------------------

metadata = MetaData(naming_convention=NAMING_CONVENTION)

# --------------------------------------------
# Declarative ORM base
# --------------------------------------------


class Base(DeclarativeBase):
    """
    Base class for all application ORM models.
    Future models should inherit from Base.
    Example:

        class HealthIssue(Base):
            __tablename__ = "health_issues"

            ...

    SQLAlchemy tracks model table definitions
    through Base.metadata.

    Alembic will use this metadata when
    generating migrations in Phase 04.
    """

    metadata = metadata
