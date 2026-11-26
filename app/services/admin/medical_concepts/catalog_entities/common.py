"""Phase 11 - Catalog service interfaces."""

from sqlalchemy.orm import Session

from app.schemas.medical_concepts.catalog_entities.common import CatalogKind
from app.services.admin.medical_concepts.clinical_entities.common import (
    list_approved_entities,
)


def get_approved_catalog(db: Session, *, kind: CatalogKind):
    """Return approved catalog metadata.

    Catalog approval does not establish clinical efficacy,
    contraindication clearance or patient suitability.
    """

    return list_approved_entities(db, kind=kind)


def get_approved_products(db: Session):
    return get_approved_catalog(db, kind="product")


def get_approved_remedies(db: Session):
    return get_approved_catalog(db, kind="remedy")


def get_approved_ingredients(db: Session):
    return get_approved_catalog(db, kind="ingredient")
