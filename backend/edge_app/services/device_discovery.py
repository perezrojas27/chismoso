"""Descubrimiento de terminales Hikvision en la LAN (no configurados)."""

from __future__ import annotations

import asyncio
import logging
from ipaddress import IPv4Address, ip_address

import httpx

from shared.config import HikvisionDevice, Settings

logger = logging.getLogger(__name__)

_DEVICE_INFO = "/ISAPI/System/deviceInfo"
# Puertos ISAPI habituales (HTTP / SDK web)
_PORTS = (80, 8000)
# Ventana de últimos octetos alrededor de cada host conocido
_NEIGHBOR_RADIUS = 12


def _candidate_hosts(configured: list[HikvisionDevice]) -> list[tuple[str, int]]:
    """Genera IPs candidatas en la misma subred /24 de los equipos ya conocidos."""
    seen: set[tuple[str, int]] = set()
    known_hosts = {d.host.strip() for d in configured}

    for device in configured:
        host = (device.host or "").strip()
        try:
            ip = ip_address(host)
        except ValueError:
            continue
        if not isinstance(ip, IPv4Address):
            continue

        parts = host.split(".")
        if len(parts) != 4:
            continue
        prefix = ".".join(parts[:3])
        base = int(parts[3])

        # Prioridad: vecino típico Puerta Secundaria (.200 → .201)
        for offset in (1, -1, 2, -2):
            last = base + offset
            if 1 <= last <= 254:
                for port in _PORTS:
                    seen.add((f"{prefix}.{last}", port))

        for last in range(
            max(1, base - _NEIGHBOR_RADIUS),
            min(254, base + _NEIGHBOR_RADIUS) + 1,
        ):
            candidate = f"{prefix}.{last}"
            if candidate in known_hosts:
                continue
            for port in _PORTS:
                seen.add((candidate, port))

    # Quitar los ya configurados (mismo host, cualquier puerto conocido)
    configured_keys = {(d.host.strip(), d.port) for d in configured}
    configured_hosts = {d.host.strip() for d in configured}
    out: list[tuple[str, int]] = []
    for host, port in sorted(seen):
        if host in configured_hosts:
            continue
        if (host, port) in configured_keys:
            continue
        out.append((host, port))
    return out


async def _probe_isapi_presence(host: str, port: int, use_https: bool) -> dict | None:
    """
    Detecta un Hikvision si responde Digest/401 o deviceInfo.
    No usa credenciales: solo presencia en red.
    """
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{host}:{port}{_DEVICE_INFO}"
    try:
        async with httpx.AsyncClient(timeout=1.8, verify=False) as client:
            response = await client.get(url)
    except httpx.RequestError:
        return None

    www = (response.headers.get("www-authenticate") or "").lower()
    body = response.text or ""
    looks_hik = (
        "digest" in www
        or "hikvision" in body.lower()
        or "<deviceName>" in body
        or '"deviceName"' in body
        or "<model>" in body
    )
    if response.status_code == 401 and ("digest" in www or looks_hik):
        label = None
    elif response.status_code < 400 and looks_hik:
        label = None
        for tag in ("deviceName", "model"):
            open_t, close_t = f"<{tag}>", f"</{tag}>"
            if open_t in body and close_t in body:
                start = body.index(open_t) + len(open_t)
                end = body.index(close_t, start)
                value = body[start:end].strip()
                if value:
                    label = value
                    break
    else:
        return None

    last = host.rsplit(".", 1)[-1]
    device_id = f"BIO-{last}"
    return {
        "device_id": device_id,
        "host": host,
        "port": port,
        "reachable": True,
        "auth_ok": False,
        "online": False,
        "connection_established": False,
        "configured": False,
        "origin": "discovered",
        "removable": False,
        "device_label": label,
        "error": "Detectado en red · no configurado",
        "status_message": "Conexión fallida",
        "search": None,
    }


async def discover_unconfigured_hikvision(
    settings: Settings,
    configured: list[HikvisionDevice] | None = None,
) -> list[dict]:
    """
    Escanea vecinos de los hosts configurados y devuelve terminales
    Hikvision presentes pero aún no dados de alta en la app.
    """
    devices = configured if configured is not None else settings.parsed_hikvision_devices()
    if not devices:
        return []

    candidates = _candidate_hosts(devices)
    if not candidates:
        return []

    logger.info(
        "Descubrimiento ISAPI: %s candidatos alrededor de %s",
        len(candidates),
        ", ".join(sorted({d.host for d in devices})),
    )

    results = await asyncio.gather(
        *[
            _probe_isapi_presence(host, port, settings.hikvision_use_https)
            for host, port in candidates
        ]
    )

    found: list[dict] = []
    seen_hosts: set[str] = set()
    for item in results:
        if not item:
            continue
        host = item["host"]
        # Preferir puerto 80 si ambos responden
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        found.append(item)

    found.sort(key=lambda d: d["host"])
    return found


def _candidates_from_seed(seed_host: str) -> list[tuple[str, int]]:
    host = (seed_host or "").strip()
    try:
        ip = ip_address(host)
    except ValueError:
        return []
    if not isinstance(ip, IPv4Address):
        return []
    parts = host.split(".")
    if len(parts) != 4:
        return []
    prefix = ".".join(parts[:3])
    base = int(parts[3])
    seen: set[tuple[str, int]] = set()
    # Incluye la propia semilla + vecindario amplio
    for last in range(max(1, base - 30), min(254, base + 30) + 1):
        for port in _PORTS:
            seen.add((f"{prefix}.{last}", port))
    return sorted(seen)


async def discover_around_host(
    settings: Settings,
    seed_host: str,
    configured: list[HikvisionDevice] | None = None,
) -> list[dict]:
    """Escaneo dirigido desde una IP semilla (consola de sede)."""
    configured = configured or []
    configured_hosts = {d.host.strip() for d in configured}
    candidates = [
        (h, p)
        for h, p in _candidates_from_seed(seed_host)
        if h not in configured_hosts
    ]
    if not candidates:
        return []

    logger.info(
        "Escaneo ISAPI desde semilla %s: %s candidatos",
        seed_host,
        len(candidates),
    )
    results = await asyncio.gather(
        *[
            _probe_isapi_presence(h, p, settings.hikvision_use_https)
            for h, p in candidates
        ]
    )
    found: list[dict] = []
    seen_hosts: set[str] = set()
    for item in results:
        if not item:
            continue
        host = item["host"]
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        found.append(item)
    found.sort(key=lambda d: d["host"])
    return found
