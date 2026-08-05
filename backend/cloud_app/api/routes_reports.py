from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from shared.config import Settings, get_settings
from shared.security import (
    ROLES_ASISTENCIA,
    ROLES_COMEDOR,
    require_roles,
    user_can_manage_gth,
)
from cloud_app.services.cafeteria_exceptions import get_cafeteria_exception_store
from shared.services.event_cleaner import clean_events
from shared.services.exceptions import (
    AuthenticationErrorBiometric,
    BiometricError,
    ConnectionErrorBiometric,
    EmptyResponseError,
)
from edge_app.services.hikvision_connector import create_event_source
from cloud_app.services.pdf_exporter import build_attendance_pdf, build_cafeteria_pdf
from cloud_app.services.report_generator import ReportGenerator
from shared.models.reports import AttendanceReport, CafeteriaEmployee, CafeteriaReport

router = APIRouter(
    prefix="/api/biometrico/reports",
    tags=["reports"],
)


def _cafeteria_for_servicios(report: CafeteriaReport) -> CafeteriaReport:
    """Listado limpio: incluye a quienes GTH ya autorizó, sin metadatos de excepción."""
    return report.model_copy(
        update={
            "exceptions_count": 0,
            "employees": [
                CafeteriaEmployee(
                    employee_id=e.employee_id,
                    employee_name=e.employee_name,
                    department=e.department,
                    marked_time=e.marked_time,
                    observation="",
                    has_exception=False,
                )
                for e in report.employees
            ],
        }
    )


def _http_from_biometric(exc: BiometricError) -> HTTPException:
    status = 502
    if isinstance(exc, AuthenticationErrorBiometric):
        status = 401
    elif isinstance(exc, EmptyResponseError):
        status = 404
    elif isinstance(exc, ConnectionErrorBiometric):
        status = 502
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


def _reject_future_dates(*dates: date) -> None:
    today = date.today()
    for d in dates:
        if d > today:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "future_date",
                    "message": (
                        "No se permiten fechas posteriores a hoy "
                        f"({today.strftime('%d/%m/%Y')})"
                    ),
                },
            )


def _reject_invalid_range(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_range",
                "message": "La fecha inicial no puede ser posterior a la final",
            },
        )
    _reject_future_dates(from_date, to_date)


async def _load_clean_events(
    settings: Settings,
    from_date: date,
    to_date: date,
    *,
    site_id: str | None = None,
):
    """
    Reportes leen del store (guía edge/cloud).
    Si AUTO_SYNC_ON_REPORT=true, primero sincroniza ISAPI→SQLite.
    Modo live: conserva el comportamiento anterior (ISAPI en el request).
    """
    mode = (settings.report_data_mode or "store").strip().lower()

    if mode == "live":
        source = create_event_source(settings)
        try:
            raw = await source.fetch_events(from_date, to_date)
        except BiometricError as exc:
            raise _http_from_biometric(exc) from exc
        return clean_events(raw, default_device_id=settings.device_id)

    from edge_app.edge.sync import load_events_from_store, resolve_site_id, sync_events_from_devices

    sid = site_id or resolve_site_id(settings)
    if settings.auto_sync_on_report:
        sync_result = await sync_events_from_devices(settings, from_date, to_date)
        if not sync_result.get("ok") and sync_result.get("code"):
            # Si falla sync pero hay datos previos en store, seguimos con store
            events = load_events_from_store(settings, from_date, to_date, site_id=sid)
            if not events:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": sync_result.get("code", "sync_failed"),
                        "message": sync_result.get("error") or "Sync ISAPI falló y el store está vacío",
                    },
                )
            return events

    events = load_events_from_store(settings, from_date, to_date, site_id=sid)
    if not events and mode == "store":
        # Último intento: sync forzado
        await sync_events_from_devices(settings, from_date, to_date)
        events = load_events_from_store(settings, from_date, to_date, site_id=sid)
    return events


@router.get("/attendance", response_model=AttendanceReport)
async def attendance_report(
    from_date: date = Query(..., description="Fecha inicio (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Fecha fin; default = from_date"),
    site_id: str | None = Query(None, description="Filtro de sede (UUID); default = sede del agente"),
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_ASISTENCIA)),
) -> AttendanceReport:
    end = to_date or from_date
    _reject_invalid_range(from_date, end)
    events = await _load_clean_events(settings, from_date, end, site_id=site_id)
    generator = ReportGenerator(cafeteria_cutoff=settings.cafeteria_cutoff_time)
    return generator.attendance_report(events, from_date, end)


@router.get("/cafeteria", response_model=CafeteriaReport)
async def cafeteria_report(
    report_date: date = Query(..., alias="date", description="Fecha del cierre comedor"),
    site_id: str | None = Query(None, description="Filtro de sede"),
    settings: Settings = Depends(get_settings),
    user: dict = Depends(require_roles(*ROLES_COMEDOR)),
) -> CafeteriaReport:
    _reject_future_dates(report_date)
    events = await _load_clean_events(settings, report_date, report_date, site_id=site_id)
    exceptions = get_cafeteria_exception_store().index_for_date(report_date)
    generator = ReportGenerator(
        cafeteria_cutoff=settings.cafeteria_cutoff_time,
        cafeteria_exceptions=exceptions,
    )
    report = generator.cafeteria_report(events, report_date)
    if not user_can_manage_gth(user):
        return _cafeteria_for_servicios(report)
    return report


@router.get("/attendance/pdf")
async def attendance_pdf(
    from_date: date = Query(...),
    to_date: date | None = Query(None),
    site_id: str | None = Query(None),
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_ASISTENCIA)),
) -> Response:
    end = to_date or from_date
    _reject_invalid_range(from_date, end)
    events = await _load_clean_events(settings, from_date, end, site_id=site_id)
    generator = ReportGenerator(cafeteria_cutoff=settings.cafeteria_cutoff_time)
    report = generator.attendance_report(events, from_date, end)
    pdf_bytes = build_attendance_pdf(report, settings.letterhead_path)
    filename = f"asistencia_{from_date.isoformat()}_{end.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/cafeteria/pdf")
async def cafeteria_pdf(
    report_date: date = Query(..., alias="date"),
    site_id: str | None = Query(None),
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_COMEDOR)),
) -> Response:
    _reject_future_dates(report_date)
    events = await _load_clean_events(settings, report_date, report_date, site_id=site_id)
    exceptions = get_cafeteria_exception_store().index_for_date(report_date)
    generator = ReportGenerator(
        cafeteria_cutoff=settings.cafeteria_cutoff_time,
        cafeteria_exceptions=exceptions,
    )
    report = generator.cafeteria_report(events, report_date)
    pdf_bytes = build_cafeteria_pdf(report, settings.letterhead_path)
    filename = f"comedor_{report_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
