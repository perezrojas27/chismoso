"""
Sync edge: ISAPI → store local (+ opcional push a cloud mock/INTEGRADO).
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from shared.config import Settings
from edge_app.edge.cloud_client import AGENT_VERSION, CloudAgentClient
from edge_app.edge.event_store import get_event_store
from edge_app.edge.sites import get_site_registry
from shared.services.exceptions import BiometricError, EmptyResponseError
from edge_app.services.hikvision_connector import create_event_source

logger = logging.getLogger(__name__)


def resolve_site_id(settings: Settings) -> str:
    registry = get_site_registry()
    if settings.site_id:
        site = registry.get_by_id(settings.site_id)
        if site:
            return site.id
    site = registry.ensure_default(settings.site_code, settings.site_name)
    return site.id


async def sync_events_from_devices(
    settings: Settings,
    from_date: date,
    to_date: date,
    *,
    push_to_cloud: bool = False,
) -> dict:
    """
    Pull ISAPI (o mock/pdf) → SQLite local.
    No bloquea por un solo dispositivo: MultiDevice ya agrega; errores se reportan.
    """
    site_id = resolve_site_id(settings)
    store = get_event_store()
    source = create_event_source(settings)

    try:
        raw = await source.fetch_events(from_date, to_date)
    except EmptyResponseError:
        return {
            "ok": True,
            "site_id": site_id,
            "inserted": 0,
            "duplicated": 0,
            "message": "Sin eventos en el rango",
        }
    except BiometricError as exc:
        logger.warning("Sync ISAPI falló: %s", exc.message)
        return {
            "ok": False,
            "site_id": site_id,
            "error": exc.message,
            "code": exc.code,
        }

    # Asegura device_id en raw antes de persistir
    for e in raw:
        if not (e.device_id or "").strip():
            e.device_id = settings.device_id

    result = store.upsert_raw_events(site_id, raw)
    last_ts = max((e.timestamp for e in raw if e.timestamp), default=None)
    for device in settings.parsed_hikvision_devices():
        store.set_cursor(site_id, device.device_id, last_ts)

    cloud_result = None
    if push_to_cloud and (settings.agent_credential or settings.enrollment_token):
        cloud_result = await push_outbox_to_cloud(settings, site_id)

    return {
        "ok": True,
        "site_id": site_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        **result,
        "cloud": cloud_result,
        "agent_version": AGENT_VERSION,
    }


async def push_outbox_to_cloud(settings: Settings, site_id: str) -> dict:
    store = get_event_store()
    pending = store.pending_outbox(limit=200)
    if not pending:
        return {"pushed": 0, "accepted": 0, "duplicates": 0}

    payload = []
    id_map: list[str] = []
    for row in pending:
        payload.append(
            {
                "device_id": row["device_id"],
                "external_event_id": row["external_event_id"],
                "occurred_at": row["occurred_at"],
                "person_external_id": row["person_external_id"],
                "person_name": row["person_name"],
                "employee_code": row["employee_code"] or row["person_external_id"],
                "event_type": row["event_type"] or "unknown",
                "success": bool(row["success"]),
            }
        )
        id_map.append(row["id"])

    client = CloudAgentClient(settings)
    try:
        response = await client.ingest(site_id, payload)
    except Exception as exc:
        logger.warning("Ingest cloud falló: %s", exc)
        return {"pushed": len(payload), "error": str(exc)}

    accepted = response.get("accepted") or []
    duplicates = response.get("duplicates") or []
    done_ext = set(accepted) | set(duplicates)
    done_ids = [
        eid
        for eid, row in zip(id_map, pending)
        if row["external_event_id"] in done_ext or not done_ext
    ]
    # Si el mock no detalla IDs, marca todos como ingeridos al 200 OK
    if not done_ext and response.get("ok"):
        done_ids = id_map
    store.mark_ingested(done_ids)
    return {
        "pushed": len(payload),
        "accepted": len(accepted) if accepted else len(done_ids),
        "duplicates": len(duplicates),
        "response": response,
    }


def load_events_from_store(
    settings: Settings,
    from_date: date,
    to_date: date,
    *,
    site_id: str | None = None,
):
    """Lectura para reportes (sin ISAPI). Devuelve AccessEvent limpios."""
    sid = site_id or resolve_site_id(settings)
    return get_event_store().query_access_events(sid, from_date, to_date)
