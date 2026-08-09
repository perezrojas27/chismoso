"""Persistencia / lectura de eventos de acceso en schema biometrico (Postgres)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.events import AccessEvent


def _parse_occurred_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("occurred_at vacío")
    # Acepta "Z" y espacio como separador
    normalized = raw.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def ingest_events(db: Session, site_id: str, events: list[dict[str, Any]]) -> dict[str, int]:
    """
    Inserta eventos con idempotencia UNIQUE(site_id, device_id, external_event_id).

    Cada ítem espera claves alineadas al contrato ingest:
      device_id, external_event_id, occurred_at, person_external_id,
      person_name?, employee_code?, department?, event_type?, success?
    """
    inserted = 0
    duplicates = 0
    sid = (site_id or "").strip()
    if not sid:
        return {"inserted": 0, "duplicates": 0}

    for raw in events:
        device_id = str(raw.get("device_id") or "").strip()
        external_id = str(raw.get("external_event_id") or "").strip()
        person_id = str(raw.get("person_external_id") or "").strip()
        if not device_id or not external_id or not person_id:
            continue
        try:
            occurred_at = _parse_occurred_at(raw.get("occurred_at"))
        except (TypeError, ValueError):
            continue

        success = raw.get("success", True)
        if isinstance(success, str):
            success = success.strip().lower() in ("1", "true", "yes", "si", "sí")

        try:
            with db.begin_nested():
                db.execute(
                    text(
                        """
                        INSERT INTO biometrico.events (
                            id, site_id, device_id, external_event_id, occurred_at,
                            person_external_id, person_name, employee_code, department,
                            event_type, success, created_at
                        ) VALUES (
                            :id, :site_id, :device_id, :external_event_id, :occurred_at,
                            :person_external_id, :person_name, :employee_code, :department,
                            :event_type, :success, NOW()
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "site_id": sid,
                        "device_id": device_id,
                        "external_event_id": external_id,
                        "occurred_at": occurred_at,
                        "person_external_id": person_id,
                        "person_name": str(raw.get("person_name") or "").strip(),
                        "employee_code": str(raw.get("employee_code") or "").strip(),
                        "department": str(raw.get("department") or "").strip(),
                        "event_type": str(raw.get("event_type") or "unknown").strip() or "unknown",
                        "success": bool(success),
                    },
                )
            inserted += 1
        except IntegrityError:
            duplicates += 1

    db.commit()
    return {"inserted": inserted, "duplicates": duplicates}


def list_events(
    db: Session,
    from_dt: datetime,
    to_dt: datetime,
    site_id: str | None = None,
) -> list[AccessEvent]:
    """Lista eventos exitosos en rango, mapeados a AccessEvent."""
    params: dict[str, Any] = {"from_dt": from_dt, "to_dt": to_dt}
    where_site = ""
    if site_id:
        where_site = "AND site_id = :site_id"
        params["site_id"] = site_id.strip()

    rows = db.execute(
        text(
            f"""
            SELECT person_external_id, person_name, department, occurred_at, device_id
            FROM biometrico.events
            WHERE success = TRUE
              AND occurred_at >= :from_dt
              AND occurred_at <= :to_dt
              {where_site}
            ORDER BY occurred_at ASC
            """
        ),
        params,
    ).mappings().all()

    events: list[AccessEvent] = []
    for row in rows:
        emp_id = str(row["person_external_id"] or "").strip()
        if not emp_id:
            continue
        emp_name = str(row["person_name"] or "").strip() or emp_id
        occurred = row["occurred_at"]
        if not isinstance(occurred, datetime):
            continue
        events.append(
            AccessEvent(
                employee_id=emp_id,
                employee_name=emp_name,
                department=str(row["department"] or "").strip(),
                timestamp=occurred,
                device_id=str(row["device_id"] or "").strip(),
            )
        )
    return events
