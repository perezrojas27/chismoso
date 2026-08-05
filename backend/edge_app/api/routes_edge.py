"""Rutas del agente edge: sync ISAPI→store, sitios, push cloud, salud."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.config import Settings, get_settings
from edge_app.edge.cloud_client import AGENT_VERSION, CloudAgentClient
from edge_app.edge.event_store import get_event_store
from edge_app.edge.sites import get_site_registry
from edge_app.edge.sync import push_outbox_to_cloud, resolve_site_id, sync_events_from_devices
from shared.security import ROLES_DEVICES, require_roles

router = APIRouter(prefix="/api/biometrico/edge", tags=["edge"])


@router.get("/sites")
async def list_sites(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles("servicios_generales", "gth", "admin", "consulta", "operador")),
) -> dict:
    sites = get_site_registry().list_sites()
    current = resolve_site_id(settings)
    return {
        "current_site_id": current,
        "site_code": settings.site_code,
        "sites": [s.model_dump() for s in sites],
        "agent_version": AGENT_VERSION,
    }


@router.post("/sync")
async def sync_now(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    push_to_cloud: bool = Query(False),
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_DEVICES, "gth", "operador")),
) -> dict:
    """Pull ISAPI → store local. Admin/GTH pueden forzar sync."""
    end = to_date or date.today()
    start = from_date or (end - timedelta(days=1))
    if end < start:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido")
    result = await sync_events_from_devices(
        settings, start, end, push_to_cloud=push_to_cloud
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post("/push")
async def push_outbox(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_DEVICES)),
) -> dict:
    site_id = resolve_site_id(settings)
    return await push_outbox_to_cloud(settings, site_id)


@router.get("/status")
async def edge_status(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_DEVICES, "gth", "operador")),
) -> dict:
    site_id = resolve_site_id(settings)
    store = get_event_store()
    stats = store.stats(site_id)
    return {
        "site_id": site_id,
        "site_code": settings.site_code,
        "agent_version": AGENT_VERSION,
        "report_data_mode": settings.report_data_mode,
        "source": settings.source,
        "integrado_base_url": settings.integrado_base_url or "(mock local)",
        "has_agent_credential": bool(settings.agent_credential),
        **stats,
    }


@router.post("/enroll")
async def enroll_agent(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_DEVICES)),
) -> dict:
    token = (settings.enrollment_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="ENROLLMENT_TOKEN no configurado")
    client = CloudAgentClient(settings)
    try:
        data = await client.enroll(token, hostname=settings.site_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return data


@router.post("/heartbeat")
async def send_heartbeat(
    settings: Settings = Depends(get_settings),
    _user: dict = Depends(require_roles(*ROLES_DEVICES)),
) -> dict:
    site_id = resolve_site_id(settings)
    store = get_event_store()
    stats = store.stats(site_id)
    devices = []
    for d in settings.parsed_hikvision_devices():
        cursor = store.get_cursor(d.device_id)
        devices.append(
            {
                "device_id": d.device_id,
                "status": "unknown",
                "last_event_at": (cursor or {}).get("last_event_at"),
                "host": d.host,
            }
        )
    client = CloudAgentClient(settings)
    body = {
        "devices": devices,
        "sync": {
            "ok": True,
            "pending_events": stats["outbox_pending"],
        },
    }
    try:
        return await client.heartbeat(site_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
