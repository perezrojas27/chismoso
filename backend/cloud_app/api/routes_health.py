from fastapi import APIRouter, Depends

from shared.config import Settings, get_settings

router = APIRouter(prefix="/api/biometrico", tags=["health"])


@router.get("/health")
async def health(
    settings: Settings = Depends(get_settings),
) -> dict:
    """Probe público (paridad con otros módulos). Inventario de dispositivos: JWT en /devices."""
    source = (settings.source or "mock").strip().lower()
    has_db = bool((settings.database_url or "").strip())
    payload: dict = {
        "status": "ok",
        "source": source,
        "service": "biometrico",
        "device_id": settings.device_id,
        "site_code": settings.site_code,
        "report_data_mode": settings.report_data_mode,
        "cafeteria_cutoff": settings.cafeteria_cutoff,
        "auth_disabled": settings.auth_disabled,
        "database": "ok" if has_db else "missing",
        "client_id": settings.app_client_id,
    }

    if settings.auth_disabled:
        payload["status"] = "degraded"
        payload["auth_warning"] = "AUTH_DISABLED=true (no usar en producción)"

    if has_db:
        try:
            from sqlalchemy import text

            from shared.database import SessionLocal

            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                payload["database"] = "ok"
            finally:
                db.close()
        except Exception as exc:
            payload["database"] = "error"
            payload["database_error"] = str(exc)[:200]
            if payload["status"] == "ok":
                payload["status"] = "degraded"

    return payload
