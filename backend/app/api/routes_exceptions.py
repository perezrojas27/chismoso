"""API de excepciones de comedor (permisos GTH)."""

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.models.events import AccessEvent
from app.security import ROLES_GTH_OPS, require_roles
from app.services.cafeteria_exceptions import (
    CafeteriaException,
    CafeteriaExceptionCreate,
    get_cafeteria_exception_store,
)
from app.services.exceptions import BiometricError
from app.services.name_format import format_employee_name

router = APIRouter(prefix="/api/biometrico/exceptions/cafeteria", tags=["exceptions"])

_read = Depends(require_roles(*ROLES_GTH_OPS))
_write = Depends(require_roles(*ROLES_GTH_OPS))


def _reject_future(day: date) -> None:
    today = date.today()
    if day > today:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "future_date",
                "message": f"No se permiten fechas posteriores a hoy ({today.isoformat()})",
            },
        )


@router.get("", dependencies=[_read])
async def list_exceptions(
    day: date = Query(..., alias="date"),
) -> list[CafeteriaException]:
    _reject_future(day)
    return get_cafeteria_exception_store().list_for_date(day)


@router.post("", response_model=CafeteriaException, dependencies=[_write])
async def create_exception(body: CafeteriaExceptionCreate) -> CafeteriaException:
    _reject_future(body.date)
    emp = (body.employee_id or "").strip()
    reason = (body.reason or "").strip()
    if not emp:
        raise HTTPException(status_code=400, detail="employee_id requerido")
    if not reason:
        raise HTTPException(status_code=400, detail="Motivo del permiso requerido")
    item = CafeteriaException(
        employee_id=emp,
        date=body.date,
        reason=reason,
        registered_by=(body.registered_by or "GTH").strip() or "GTH",
    )
    return get_cafeteria_exception_store().upsert(item)


@router.delete("", dependencies=[_write])
async def delete_exception(
    day: date = Query(..., alias="date"),
    employee_id: str = Query(...),
) -> dict:
    _reject_future(day)
    ok = get_cafeteria_exception_store().delete(employee_id.strip(), day)
    if not ok:
        raise HTTPException(status_code=404, detail="Excepción no encontrada")
    return {"ok": True}


@router.get("/candidates", dependencies=[_read])
async def late_candidates(
    day: date = Query(..., alias="date"),
    site_id: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """
    Candidatos GTH: primera marca del día posterior al corte (no llegaron a tiempo).
    Quien ya marcó ≤ corte no aparece, aunque tenga marcas más tarde.
    """
    _reject_future(day)
    cutoff: time = settings.cafeteria_cutoff_time
    late_end: time = settings.cafeteria_late_end_time

    from app.api.routes_reports import _load_clean_events

    try:
        events = await _load_clean_events(settings, day, day, site_id=site_id)
    except HTTPException:
        raise
    except BiometricError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    first_of_day: dict[str, AccessEvent] = {}
    for e in events:
        if e.timestamp.date() != day:
            continue
        prev = first_of_day.get(e.employee_id)
        if prev is None or e.timestamp < prev.timestamp:
            first_of_day[e.employee_id] = e

    already = set(get_cafeteria_exception_store().index_for_date(day))
    candidates: list[dict] = []
    # Ventana GTH: después del corte (09:00) y hasta late_end (11:00)
    for emp_id, event in first_of_day.items():
        t = event.timestamp.time()
        if t <= cutoff or t > late_end:
            continue
        candidates.append(
            {
                "employee_id": emp_id,
                "employee_name": format_employee_name(event.employee_name),
                "department": event.department,
                "marked_time": event.timestamp.isoformat(),
                "has_exception": emp_id in already,
            }
        )

    candidates.sort(key=lambda x: x["marked_time"])
    return candidates
