"""
The Invisible Healer
Shared API Dependencies

Phase 01:
    Application configuration dependency.

Phase 03:
    Database session dependency.

Purpose:
    Provide reusable, typed FastAPI
    dependencies across API modules.

Future:
    - Admin authentication
    - Role-based authorization
    - Clinical scope validation
    - Patient context
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db

# ============================================
# APPLICATION SETTINGS DEPENDENCY
# ============================================

SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseSessionDependency = Annotated[Session, Depends(get_db)]
