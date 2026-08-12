"""Administración de dispositivos biométricos en el agente edge (consola de sede)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from edge_app.api.routes_edge_admin import require_edge_console_auth
from edge_app.services.device_registry import (
    ManagedDevice,
    ManagedDeviceCreate,
    get_device_registry,
    resolve_device_location,
)
from shared.config import Settings, get_settings

router = APIRouter(
    prefix="/api/biometrico/devices",
    tags=["devices"],
    dependencies=[Depends(require_edge_console_auth)],
)


class ScanBody(BaseModel):
    seed_host: str = Field(min_length=7, max_length=64)


def _status_payload(
    *,
    source: str,
    settings: Settings,
    devices: list[dict],
    message: str | None = None,
) -> dict:
    ok = sum(1 for d in devices if d.get("online"))
    total = len(devices)
    if source != "hikvision":
        status = "mock"
    elif total == 0:
        status = "empty"
    elif ok == total:
        status = "ok"
    elif ok == 0:
        status = "offline"
    else:
        status = "partial"
    return {
        "source": source,
        "user": settings.effective_hikvision_user(),
        "use_https": settings.hikvision_use_https,
        "cafeteria_cutoff": settings.cafeteria_cutoff,
        "cafeteria_late_end": settings.cafeteria_late_end,
        "isapi_password_configured": bool(
            (settings.effective_hikvision_password() or "").strip()
        ),
        "read_only": False,
        "devices": devices,
        "devices_ok": ok,
        "devices_total": total,
        "status": status,
        "message": message,
    }


@router.get("")
async def list_devices(settings: Settings = Depends(get_settings)) -> dict:
    """Lista dispositivos (env + UI) y prueba conexión en línea."""
    source = (settings.source or "mock").strip().lower()
    env_ids = {d.device_id for d in settings._parse_env_hikvision_devices()}
    managed = {d.device_id: d for d in get_device_registry().list_devices()}
    managed_ids = set(managed)
    configured = settings.parsed_hikvision_devices()

    base_rows = [
        {
            "device_id": d.device_id,
            "host": d.host,
            "port": d.port,
            "location": resolve_device_location(
                d.device_id,
                managed[d.device_id].location if d.device_id in managed else None,
                host=d.host,
            ),
            "reachable": None,
            "auth_ok": None,
            "error": None,
            "online": None,
            "origin": "managed" if d.device_id in managed_ids else "env",
            "removable": d.device_id in managed_ids,
            "editable": True,
            "still_in_env": d.device_id in env_ids,
        }
        for d in configured
    ]

    if source != "hikvision":
        return _status_payload(
            source=source,
            settings=settings,
            devices=base_rows,
            message=(
                "Fuente en modo mock: no hay sonda real. "
                "Configure SOURCE=hikvision para probar conexiones."
            ),
        )

    from edge_app.services.device_discovery import discover_unconfigured_hikvision
    from edge_app.services.hikvision_connector import probe_hikvision_devices

    probed = await probe_hikvision_devices(settings)
    by_id = {d.device_id: d for d in configured}
    origin_by_id = {row["device_id"]: row for row in base_rows}
    devices: list[dict] = []
    for item in probed:
        device_id = str(item.get("device_id") or "")
        cfg = by_id.get(device_id)
        meta = origin_by_id.get(device_id, {})
        reachable = bool(item.get("reachable"))
        auth_ok = item.get("auth_ok")
        online = reachable and (auth_ok is True or auth_ok is None)
        established = bool(item.get("connection_established"))
        devices.append(
            {
                "device_id": device_id,
                "host": item.get("host") or (cfg.host if cfg else None),
                "port": (cfg.port if cfg else None) or item.get("port"),
                "location": meta.get("location")
                or resolve_device_location(
                    device_id,
                    host=item.get("host") or (cfg.host if cfg else None),
                ),
                "reachable": reachable,
                "auth_ok": auth_ok,
                "error": item.get("error"),
                "online": online,
                "connection_established": established,
                "configured": True,
                "status_message": (
                    "Conexión establecida"
                    if established
                    else ("Conexión fallida" if reachable else "Sin respuesta")
                ),
                "device_label": item.get("device_label"),
                "search": item.get("search"),
                "origin": meta.get("origin", "env"),
                "removable": bool(meta.get("removable")),
                "editable": True,
                "still_in_env": bool(meta.get("still_in_env")),
            }
        )

    seed = (settings.edge_scan_seed_host or settings.hikvision_host or "").strip()
    discovered = await discover_unconfigured_hikvision(settings, configured)
    if seed and not discovered and not configured:
        from edge_app.services.device_discovery import discover_around_host

        discovered = await discover_around_host(settings, seed, configured)

    configured_hosts = {d.host for d in configured}
    for item in discovered:
        if item["host"] in configured_hosts:
            continue
        from edge_app.services.device_registry import device_id_from_host

        suggested = device_id_from_host(item["host"])
        item["device_id"] = suggested
        item["suggested_id"] = suggested
        item["location"] = resolve_device_location(
            suggested, host=item["host"]
        ) or item.get("location") or "Ubicación por definir"
        devices.append(item)

    ok = sum(1 for d in devices if d.get("online"))
    configured_count = sum(1 for d in devices if d.get("configured"))
    discovered_count = sum(1 for d in devices if not d.get("configured"))

    message = None
    if not devices:
        message = (
            "No hay dispositivos configurados ni detectados. "
            "Use «Buscar en la red» con una IP cercana (ej. 192.168.10.200)."
        )
    elif discovered_count:
        message = (
            f"{discovered_count} dispositivo(s) detectado(s) sin configurar. "
            "Agrégalos desde este panel para activar la conexión."
        )
    elif not (settings.effective_hikvision_password() or "").strip():
        message = (
            "Hay equipos listados, pero falta la contraseña ISAPI del reloj. "
            "Guárdala en «Credenciales del reloj»."
        )

    payload = _status_payload(
        source=source,
        settings=settings,
        devices=devices,
        message=message,
    )
    payload["devices_ok"] = ok
    payload["devices_total"] = len(devices)
    payload["configured_count"] = configured_count
    payload["discovered_count"] = discovered_count
    if discovered_count and ok == configured_count and configured_count > 0:
        payload["status"] = "partial"
    return payload


@router.post("/scan")
async def scan_network(
    body: ScanBody,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Busca relojes Hikvision alrededor de una IP semilla."""
    from edge_app.services.device_discovery import discover_around_host
    from edge_app.services.device_registry import device_id_from_host

    configured = settings.parsed_hikvision_devices()
    found = await discover_around_host(settings, body.seed_host.strip(), configured)
    devices = []
    for item in found:
        suggested = device_id_from_host(item["host"])
        devices.append(
            {
                **item,
                "device_id": suggested,
                "suggested_id": suggested,
                "configured": False,
                "location": resolve_device_location(suggested, host=item["host"])
                or "Ubicación por definir",
            }
        )
    return {
        "seed_host": body.seed_host.strip(),
        "found": len(devices),
        "devices": devices,
        "message": (
            f"Se detectaron {len(devices)} equipo(s) cerca de {body.seed_host.strip()}."
            if devices
            else f"No se detectaron equipos cerca de {body.seed_host.strip()}."
        ),
    }


@router.post("")
async def create_device(
    body: ManagedDeviceCreate,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Agrega o actualiza un dispositivo administrable (persistido en data/)."""
    try:
        payload = body.model_dump()
        if not (payload.get("device_id") or "").strip():
            from edge_app.services.device_registry import device_id_from_host

            payload["device_id"] = device_id_from_host(str(payload.get("host") or ""))
        device = ManagedDevice.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else None
        msg = str(first.get("msg") if first else exc)
        raise HTTPException(status_code=400, detail=msg) from exc

    env_ids = {d.device_id for d in settings._parse_env_hikvision_devices()}
    saved = get_device_registry().upsert(device)
    return {
        "device": saved.model_dump(),
        "origin": "managed",
        "overrides_env": saved.device_id in env_ids,
        "message": (
            f"Dispositivo {saved.device_id} guardado. "
            + (
                "Sobrescribe la entrada del .env con el mismo ID."
                if saved.device_id in env_ids
                else "Quedará disponible en reportes y sondas."
            )
        ),
    }


@router.put("/{device_id}")
async def update_device(
    device_id: str,
    body: ManagedDeviceCreate,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Edita un dispositivo manteniendo el ID interno (host/puerto/ubicación)."""
    key = device_id.strip().upper()
    env_ids = {d.device_id for d in settings._parse_env_hikvision_devices()}
    managed_ids = {d.device_id for d in get_device_registry().list_devices()}
    known = env_ids | managed_ids | {
        d.device_id for d in settings.parsed_hikvision_devices()
    }
    if key not in known:
        raise HTTPException(status_code=404, detail=f"Dispositivo {key} no encontrado")

    try:
        payload = body.model_dump()
        payload["device_id"] = key
        device = ManagedDevice.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else None
        msg = str(first.get("msg") if first else exc)
        raise HTTPException(status_code=400, detail=msg) from exc

    saved = get_device_registry().upsert(device)
    return {
        "device": saved.model_dump(),
        "origin": "managed",
        "overrides_env": key in env_ids,
        "message": (
            f"Dispositivo {key} actualizado"
            + (" (sobrescribe .env)" if key in env_ids else "")
            + "."
        ),
    }


@router.post("/{device_id}/probe")
async def probe_device(
    device_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Sonda ISAPI de un solo dispositivo configurado."""
    key = device_id.strip().upper()
    devices = {d.device_id: d for d in settings.parsed_hikvision_devices()}
    cfg = devices.get(key)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Dispositivo {key} no encontrado")

    source = (settings.source or "mock").strip().lower()
    if source != "hikvision":
        return {
            "device_id": key,
            "online": False,
            "message": "Fuente en modo mock: no hay sonda real.",
        }

    from edge_app.services.hikvision_connector import HikvisionConnector

    connector = HikvisionConnector(
        settings,
        device_id=cfg.device_id,
        host=cfg.host,
        port=cfg.port,
    )
    item = await connector.probe()
    reachable = bool(item.get("reachable"))
    auth_ok = item.get("auth_ok")
    online = reachable and (auth_ok is True or auth_ok is None)
    if online:
        message = "Conexión establecida"
    elif reachable and auth_ok is False:
        message = "Clave ISAPI incorrecta"
    else:
        message = item.get("error") or "Sin conexión"
    return {
        "device_id": key,
        "host": item.get("host") or cfg.host,
        "port": cfg.port,
        "reachable": reachable,
        "auth_ok": auth_ok,
        "online": online,
        "device_label": item.get("device_label"),
        "error": item.get("error"),
        "message": message,
    }


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Elimina un dispositivo agregado desde la UI (no borra entradas solo de .env)."""
    key = device_id.strip().upper()
    env_ids = {d.device_id for d in settings._parse_env_hikvision_devices()}
    managed_ids = {d.device_id for d in get_device_registry().list_devices()}

    if key not in managed_ids:
        if key in env_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{key} está definido en HIKVISION_DEVICES (.env). "
                    "Edítelo desde este panel (queda en registro UI) o elimínelo del .env."
                ),
            )
        raise HTTPException(status_code=404, detail=f"Dispositivo {key} no encontrado")

    get_device_registry().delete(key)
    still_in_env = key in env_ids
    return {
        "deleted": key,
        "still_in_env": still_in_env,
        "message": (
            f"{key} eliminado del registro UI."
            + (" Sigue activo vía .env." if still_in_env else "")
        ),
    }
