"""
Bucle operativo del agente: enroll (si hace falta) + heartbeat (+ sync ISAPI opcional).
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import date, timedelta

from shared.config import Settings, get_settings
from edge_app.edge.cloud_client import AGENT_VERSION, CloudAgentClient
from edge_app.edge.event_store import get_event_store
from edge_app.edge.state_store import load_state, save_state
from edge_app.edge.sync import push_outbox_to_cloud, resolve_site_id, sync_events_from_devices
from edge_app.services.hikvision_connector import probe_hikvision_devices

logger = logging.getLogger(__name__)


def _apply_persisted_credentials(settings: Settings) -> Settings:
    """Inyecta SITE_ID / AGENT_CREDENTIAL desde /data si el env aún no los trae."""
    state = load_state()
    updates: dict = {}
    if not (settings.agent_credential or "").strip() and state.get("agent_credential"):
        updates["agent_credential"] = state["agent_credential"]
    if not (settings.site_id or "").strip() and state.get("site_id"):
        updates["site_id"] = state["site_id"]
    if updates:
        return settings.model_copy(update=updates)
    return settings


async def ensure_enrolled(settings: Settings) -> Settings:
    settings = _apply_persisted_credentials(settings)
    if (settings.agent_credential or "").strip() and (settings.site_id or "").strip():
        return settings

    token = (settings.enrollment_token or "").strip()
    base = (settings.integrado_base_url or "").strip()
    if not token or not base:
        logger.warning(
            "Edge sin enroll: faltan INTEGRADO_BASE_URL o ENROLLMENT_TOKEN "
            "(y no hay AGENT_CREDENTIAL persistido)"
        )
        return settings

    hostname = socket.gethostname()
    client = CloudAgentClient(settings)
    logger.info("Enrolling edge → %s (site_code=%s)", base, settings.site_code)
    data = await client.enroll(token, hostname=hostname or settings.site_code)
    site_id = str(data.get("site_id") or "").strip()
    credential = str(data.get("agent_credential") or "").strip()
    if not site_id or not credential:
        raise RuntimeError(f"Respuesta enroll incompleta: {data}")

    save_state(
        {
            "site_id": site_id,
            "site_code": data.get("site_code") or settings.site_code,
            "agent_credential": credential,
            "agent_version": AGENT_VERSION,
        }
    )
    logger.info("Enroll OK site_id=%s", site_id)
    return settings.model_copy(
        update={"site_id": site_id, "agent_credential": credential}
    )


async def send_heartbeat_once(settings: Settings) -> dict:
    settings = _apply_persisted_credentials(settings)
    site_id = (settings.site_id or "").strip() or resolve_site_id(settings)
    store = get_event_store()
    stats = store.stats(site_id)

    devices: list[dict] = []
    source = (settings.source or "").strip().lower()
    if source == "hikvision" and (settings.effective_hikvision_password() or "").strip():
        try:
            probed = await probe_hikvision_devices(settings)
            for d in probed:
                devices.append(
                    {
                        "device_id": d.get("device_id"),
                        "host": d.get("host") or "",
                        "port": d.get("port") or 80,
                        "status": "online" if d.get("reachable") else "offline",
                        "last_event_at": None,
                    }
                )
        except Exception as exc:
            logger.warning("Probe ISAPI falló (heartbeat con config): %s", exc)

    if not devices:
        for d in settings.parsed_hikvision_devices():
            cursor = store.get_cursor(d.device_id)
            devices.append(
                {
                    "device_id": d.device_id,
                    "host": d.host,
                    "port": d.port,
                    "status": "configured",
                    "last_event_at": (cursor or {}).get("last_event_at"),
                }
            )

    client = CloudAgentClient(settings)
    body = {
        "devices": devices,
        "sync": {"ok": True, "pending_events": stats.get("outbox_pending", 0)},
    }
    return await client.heartbeat(site_id, body)


async def sync_and_push_once(settings: Settings) -> dict:
    settings = _apply_persisted_credentials(settings)
    end = date.today()
    start = end - timedelta(days=int(os.environ.get("EDGE_SYNC_LOOKBACK_DAYS", "2")))
    result = await sync_events_from_devices(
        settings, start, end, push_to_cloud=False
    )
    site_id = (settings.site_id or "").strip() or resolve_site_id(settings)
    if settings.agent_credential:
        cloud = await push_outbox_to_cloud(settings, site_id)
        result["cloud"] = cloud
    return result


async def runtime_loop(stop: asyncio.Event) -> None:
    """Enroll al arranque; heartbeat periódico; sync ISAPI si hay password."""
    interval = max(30, int(os.environ.get("EDGE_HEARTBEAT_SECONDS", "60")))
    sync_every = max(1, int(os.environ.get("EDGE_SYNC_EVERY_N", "5")))
    cycle = 0

    try:
        settings = await ensure_enrolled(get_settings())
    except Exception as exc:
        logger.error("Enroll inicial falló: %s", exc)
        settings = get_settings()

    while not stop.is_set():
        cycle += 1
        try:
            settings = _apply_persisted_credentials(get_settings())
            if not (settings.agent_credential or "").strip():
                settings = await ensure_enrolled(settings)

            if (settings.agent_credential or "").strip():
                hb = await send_heartbeat_once(settings)
                logger.info("Heartbeat OK → %s", hb)

                do_sync = (settings.source or "").lower() == "hikvision" and bool(
                    (settings.effective_hikvision_password() or "").strip()
                )
                if do_sync and cycle % sync_every == 0:
                    sync_res = await sync_and_push_once(settings)
                    logger.info("Sync/push: %s", sync_res)
            else:
                logger.warning("Sin credencial de agente; reintento enroll en %ss", interval)
        except Exception as exc:
            logger.exception("Ciclo edge falló: %s", exc)

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
