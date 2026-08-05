from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.security import require_app_access

router = APIRouter(prefix="/api/biometrico", tags=["health"])


@router.get("/health")
async def health(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_app_access),
) -> dict:
    source = (settings.source or "mock").strip().lower()
    devices = [
        {
            "device_id": d.device_id,
            "host": d.host,
            "port": d.port,
            "reachable": None,
            "error": None,
        }
        for d in settings.parsed_hikvision_devices()
    ]
    payload: dict = {
        "status": "ok",
        "source": source,
        "device_id": settings.device_id,
        "site_code": settings.site_code,
        "report_data_mode": settings.report_data_mode,
        "cafeteria_cutoff": settings.cafeteria_cutoff,
        "devices": devices,
        "auth_disabled": settings.auth_disabled,
        "client_id": settings.app_client_id,
    }

    try:
        from app.edge.sync import resolve_site_id
        from app.edge.event_store import get_event_store

        sid = resolve_site_id(settings)
        payload["site_id"] = sid
        payload["event_store"] = get_event_store().stats(sid)
    except Exception:
        pass

    if source == "hikvision":
        from app.services.hikvision_connector import probe_hikvision_devices

        probed = await probe_hikvision_devices(settings)
        payload["devices"] = probed
        reachable = [d for d in probed if d.get("reachable")]
        payload["devices_ok"] = len(reachable)
        payload["devices_total"] = len(probed)
        if not reachable:
            payload["status"] = "degraded"
        elif len(reachable) < len(probed):
            payload["status"] = "partial"

    return payload
