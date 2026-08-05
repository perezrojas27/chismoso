"""
Limpieza y normalización de eventos de acceso.

Transformaciones:
1. Conservar solo autenticaciones / asistencias exitosas.
2. Eliminar marcas duplicadas del mismo empleado en el mismo minuto.
3. Mapear a AccessEvent limpio: employee_id, employee_name, department, timestamp, device_id.
"""

from __future__ import annotations

from shared.models.events import AccessEvent, RawAccessEvent
from edge_app.services.hikvision_connector import resolve_department
from shared.services.name_format import format_employee_name

# major=5 en AcsEvent de Hikvision suele indicar eventos de autenticación.
_AUTH_MAJOR_CODES = {5}


def is_successful_auth(raw: RawAccessEvent) -> bool:
    """True si el evento representa una autenticación/asistencia exitosa."""
    if not raw.success:
        return False
    if raw.timestamp is None:
        return False
    if not (raw.employee_id or "").strip():
        return False
    # Si viene major desde ISAPI, filtrar por códigos de autenticación.
    if raw.major is not None and raw.major not in _AUTH_MAJOR_CODES:
        return False
    return True


def clean_events(raw_events: list[RawAccessEvent], default_device_id: str = "BIO-01") -> list[AccessEvent]:
    """
    Filtra éxitos, deduplica por (employee_id, minuto) y ordena por timestamp.

    Regla de dedupe: si un usuario marca varias veces en el mismo minuto,
    se conserva solo la primera marca de ese minuto.
    """
    successful: list[AccessEvent] = []
    for raw in raw_events:
        if not is_successful_auth(raw):
            continue
        assert raw.timestamp is not None
        dept = (raw.department or "").strip()
        if not dept:
            dept = resolve_department(raw.employee_id, raw.employee_name or "")
        successful.append(
            AccessEvent(
                employee_id=raw.employee_id.strip(),
                employee_name=format_employee_name(
                    (raw.employee_name or raw.employee_id).strip()
                ),
                department=dept,
                timestamp=raw.timestamp,
                device_id=(raw.device_id or default_device_id).strip(),
            )
        )

    successful.sort(key=lambda e: (e.employee_id, e.timestamp))

    deduped: list[AccessEvent] = []
    seen_minute_keys: set[tuple[str, str]] = set()
    for event in successful:
        # Clave: empleado + minuto calendario (YYYY-MM-DD HH:MM)
        minute_key = (event.employee_id, event.timestamp.strftime("%Y-%m-%d %H:%M"))
        if minute_key in seen_minute_keys:
            continue
        seen_minute_keys.add(minute_key)
        deduped.append(event)

    deduped.sort(key=lambda e: e.timestamp)
    return deduped
