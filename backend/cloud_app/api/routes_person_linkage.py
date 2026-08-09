"""API — vinculación persona biométrica (employeeNo) ↔ empleado GTH."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from cloud_app.services.person_gth_linkage import (
    link_person_to_employee,
    list_active_employees_bio_linkage,
    list_unlinked_persons_from_events,
    presence_report,
    unlink_person_from_employee,
)
from shared.database import get_db
from shared.security import ROLES_GTH_OPS, require_roles

router = APIRouter(
    prefix="/api/biometrico/person-linkage",
    tags=["person-linkage"],
)


class LinkPersonBody(BaseModel):
    person_external_id: str = Field(..., min_length=1, max_length=128)
    notes: str = Field(default="", max_length=500)


@router.get("/active")
def get_active_employee_bio_linkage(
    q: Optional[str] = Query(default=None),
    link_filter: Literal["all", "linked", "unlinked"] = Query(default="all"),
    site_id: Optional[str] = Query(default=None, description="UUID core.sites"),
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_roles(*ROLES_GTH_OPS)),
    db: Session = Depends(get_db),
):
    items, total, stats = list_active_employees_bio_linkage(
        db,
        q=q,
        link_filter=link_filter,
        site_id=site_id,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "stats": stats, "items": items}


@router.get("/persons/unlinked")
def get_unlinked_biometric_persons(
    q: Optional[str] = Query(default=None),
    site_id: Optional[str] = Query(default=None, description="site_id biométrico (edge)"),
    limit: int = Query(default=80, ge=1, le=200),
    _: dict = Depends(require_roles(*ROLES_GTH_OPS)),
    db: Session = Depends(get_db),
):
    items = list_unlinked_persons_from_events(db, q=q, site_id=site_id, limit=limit)
    return {"count": len(items), "items": items}


@router.post("/{employee_id}/link")
def link_biometric_person(
    employee_id: str,
    body: LinkPersonBody,
    user: dict = Depends(require_roles(*ROLES_GTH_OPS)),
    db: Session = Depends(get_db),
):
    payload = user.get("payload") or {}
    try:
        result = link_person_to_employee(
            db,
            employee_id=employee_id,
            person_external_id=body.person_external_id,
            linked_by=str(payload.get("sub") or ""),
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/{employee_id}/unlink")
def unlink_biometric_person(
    employee_id: str,
    _: dict = Depends(require_roles(*ROLES_GTH_OPS)),
    db: Session = Depends(get_db),
):
    try:
        return unlink_person_from_employee(db, employee_id=employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/presence")
def get_presence_by_gth_site(
    date: str = Query(..., description="YYYY-MM-DD"),
    core_site_id: str = Query(..., description="UUID core.sites"),
    biometric_site_id: Optional[str] = Query(
        default=None,
        description="Opcional: forzar site_id del edge; si no, usa biometrico.site_map",
    ),
    _: dict = Depends(require_roles(*ROLES_GTH_OPS)),
    db: Session = Depends(get_db),
):
    try:
        return presence_report(
            db,
            day=date,
            core_site_id=core_site_id,
            biometric_site_id=biometric_site_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
