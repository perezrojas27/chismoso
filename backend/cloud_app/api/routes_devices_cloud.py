"""Inventario de dispositivos reportados por agentes (solo lectura en cloud)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.security import ROLES_DEVICES, require_roles

router = APIRouter(prefix="/api/biometrico/devices", tags=["devices-cloud"])


@router.get("")
def list_reported_devices(
    _: dict = Depends(require_roles(*ROLES_DEVICES)),
    db: Session = Depends(get_db),
):
    """Dispositivos vistos vía heartbeat de agentes (CRUD ISAPI vive en el edge)."""
    rows = db.execute(
        text(
            """
            SELECT d.device_id, d.host, d.status, d.last_seen_at, d.last_event_at,
                   d.meta, d.site_id,
                   a.site_code, a.hostname AS agent_hostname
            FROM biometrico.agent_devices d
            LEFT JOIN biometrico.agents a ON a.id = d.agent_id
            ORDER BY d.last_seen_at DESC NULLS LAST, d.device_id
            """
        )
    ).mappings().all()

    devices = []
    ok = 0
    for r in rows:
        meta = r["meta"] if isinstance(r["meta"], dict) else {}
        port = meta.get("port") if isinstance(meta.get("port"), int) else 80
        online = str(r["status"] or "").lower() in ("online", "ok", "up")
        if online:
            ok += 1
        devices.append(
            {
                "device_id": r["device_id"],
                "host": r["host"] or "",
                "port": port,
                "location": (r["site_code"] or r["site_id"] or ""),
                "reachable": online,
                "online": online,
                "error": None,
                "origin": "agent",
                "removable": False,
                "managed_on": "edge",
                "site_id": r["site_id"],
                "agent_hostname": r["agent_hostname"],
                "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
                "last_event_at": r["last_event_at"].isoformat() if r["last_event_at"] else None,
                "status": r["status"],
                "connection_established": online,
                "status_message": (
                    "Reportado por agente edge (heartbeat)"
                    if online
                    else "Reportado por agente; ISAPI aún no verificado o sin password"
                ),
                "configured": True,
            }
        )

    status = "ok" if devices and ok == len(devices) else (
        "partial" if devices and ok else ("empty" if not devices else "offline")
    )
    return {
        "status": status,
        "source": "agent_heartbeat",
        "user": "",
        "use_https": False,
        "cafeteria_cutoff": "",
        "cafeteria_late_end": "",
        "devices": devices,
        "devices_ok": ok,
        "devices_total": len(devices),
        "read_only": True,
        "message": (
            "Inventario reportado por agentes edge. "
            "Alta/baja ISAPI se gestiona en el agente de sede."
        ),
    }
