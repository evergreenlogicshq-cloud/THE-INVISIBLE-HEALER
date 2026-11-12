
"""
The Invisible Healer
Shared FastAPI Dependencies

Responsibilities:
    - Expose reusable dependency providers.
    - Separate route definitions from configuration.
    - Provide consistent dependency injection.
    - Support dependency overrides in tests.

Phase:
    01 - Project Skeleton

Future additions:
    - Database session dependency.
    - Authenticated admin dependency.
    - Role permission dependency.
    - Request context dependency.
"""

from typing import Annotated
from fastapi import Depends
from app.core.config import Settings, get_settings


# -----------------------------------------
# Application configuration dependency
# -----------------------------------------

SettingsDependency = Annotated[Settings, Depends(get_settings)]
