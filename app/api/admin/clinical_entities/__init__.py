"""Phase 10 - Clinical entity router registry."""

from fastapi import APIRouter

from app.api.admin.clinical_entities.health_issue import router as health_issue_router
from app.api.admin.clinical_entities.symptom import router as symptom_router

router = APIRouter()

router.include_router(health_issue_router)
router.include_router(symptom_router)
