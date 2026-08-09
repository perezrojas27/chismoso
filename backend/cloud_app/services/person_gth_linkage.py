"""Vinculación employeeNo (reloj) ↔ hr.employees — dueño schema biometrico."""
from __future__ import annotations

import re
import uuid
from typing import Any, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _norm_cedula(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"[\s.\-]", "", str(raw).strip().upper())


def list_active_employees_bio_linkage(
    db: Session,
    *,
    q: Optional[str] = None,
    link_filter: Literal["all", "linked", "unlinked"] = "all",
    site_id: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    where = ["e.is_active IS TRUE"]
    if q and q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append(
            "(e.cedula ILIKE :q OR e.first_name ILIKE :q OR e.last_name ILIKE :q "
            "OR CONCAT(e.first_name, ' ', e.last_name) ILIKE :q)"
        )
    if site_id and site_id.strip():
        params["site_id"] = site_id.strip()
        where.append("e.site_id::text = :site_id")

    where_sql = " AND ".join(where)
    link_join = "LEFT JOIN biometrico.person_links pl ON pl.employee_id = e.id"

    if link_filter == "linked":
        where_sql += " AND pl.id IS NOT NULL"
    elif link_filter == "unlinked":
        where_sql += " AND pl.id IS NULL"

    count_row = db.execute(
        text(
            f"""
            SELECT COUNT(*) FROM hr.employees e
            {link_join}
            WHERE {where_sql}
            """
        ),
        params,
    ).scalar()
    total = int(count_row or 0)

    stats = db.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE e.is_active IS TRUE) AS active,
              COUNT(*) FILTER (WHERE e.is_active IS TRUE AND pl.id IS NOT NULL) AS linked,
              COUNT(*) FILTER (WHERE e.is_active IS TRUE AND pl.id IS NULL) AS unlinked
            FROM hr.employees e
            LEFT JOIN biometrico.person_links pl ON pl.employee_id = e.id
            """
        )
    ).mappings().one()

    rows = db.execute(
        text(
            f"""
            SELECT e.id::text AS employee_id,
                   e.cedula,
                   e.first_name,
                   e.last_name,
                   e.site_id::text AS site_id,
                   s.name AS site_name,
                   pl.person_external_id,
                   pl.linked_at,
                   pl.linked_by
            FROM hr.employees e
            {link_join}
            LEFT JOIN core.sites s ON s.id = e.site_id
            WHERE {where_sql}
            ORDER BY e.last_name ASC, e.first_name ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = []
    for r in rows:
        items.append(
            {
                "employee_id": r["employee_id"],
                "cedula": r["cedula"] or "",
                "full_name": f"{r['first_name']} {r['last_name']}".strip(),
                "site_id": r["site_id"],
                "site_name": r["site_name"] or "",
                "linked": bool(r["person_external_id"]),
                "person_external_id": r["person_external_id"],
                "linked_at": r["linked_at"].isoformat() if r["linked_at"] else None,
                "linked_by": r["linked_by"] or "",
            }
        )
    return items, total, {
        "active": int(stats["active"] or 0),
        "linked": int(stats["linked"] or 0),
        "unlinked": int(stats["unlinked"] or 0),
    }


def list_unlinked_persons_from_events(
    db: Session,
    *,
    q: Optional[str] = None,
    site_id: Optional[str] = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    where = ["pl.id IS NULL", "TRIM(e.person_external_id) <> ''"]
    if q and q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append(
            "(e.person_external_id ILIKE :q OR e.person_name ILIKE :q OR e.employee_code ILIKE :q)"
        )
    if site_id and site_id.strip():
        params["site_id"] = site_id.strip()
        where.append("e.site_id = :site_id")

    where_sql = " AND ".join(where)
    rows = db.execute(
        text(
            f"""
            SELECT e.person_external_id,
                   MAX(e.person_name) AS person_name,
                   MAX(e.employee_code) AS employee_code,
                   COUNT(*)::int AS event_count,
                   MAX(e.occurred_at) AS last_seen
            FROM biometrico.events e
            LEFT JOIN biometrico.person_links pl
              ON pl.person_external_id = e.person_external_id
            WHERE {where_sql}
            GROUP BY e.person_external_id
            ORDER BY last_seen DESC NULLS LAST
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()
    return [
        {
            "person_external_id": r["person_external_id"],
            "person_name": r["person_name"] or "",
            "employee_code": r["employee_code"] or "",
            "event_count": r["event_count"],
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            "suggested_cedula_match": _norm_cedula(r["person_external_id"]),
        }
        for r in rows
    ]


def link_person_to_employee(
    db: Session,
    *,
    employee_id: str,
    person_external_id: str,
    linked_by: str = "",
    notes: str = "",
) -> dict[str, Any]:
    ext = (person_external_id or "").strip()
    if not ext:
        raise ValueError("person_external_id vacío")
    try:
        emp_uuid = uuid.UUID(str(employee_id))
    except ValueError as exc:
        raise ValueError("employee_id inválido") from exc

    emp = db.execute(
        text(
            """
            SELECT id::text, cedula, first_name, last_name, is_active
            FROM hr.employees WHERE id = :id
            """
        ),
        {"id": str(emp_uuid)},
    ).mappings().first()
    if not emp:
        raise ValueError("Empleado GTH no encontrado")
    if not emp["is_active"]:
        raise ValueError("El empleado GTH no está activo")

    taken_ext = db.execute(
        text(
            "SELECT employee_id::text FROM biometrico.person_links WHERE person_external_id = :ext"
        ),
        {"ext": ext},
    ).scalar()
    if taken_ext and taken_ext != str(emp_uuid):
        raise ValueError(f"El ID biométrico {ext} ya está vinculado a otro empleado")

    taken_emp = db.execute(
        text(
            "SELECT person_external_id FROM biometrico.person_links WHERE employee_id = :eid"
        ),
        {"eid": str(emp_uuid)},
    ).scalar()
    if taken_emp and taken_emp != ext:
        raise ValueError("Este empleado GTH ya tiene un ID biométrico vinculado")

    cedula = emp["cedula"] or ""
    db.execute(
        text(
            """
            INSERT INTO biometrico.person_links
              (person_external_id, employee_id, cedula, notes, linked_by)
            VALUES (:ext, :eid, :cedula, :notes, :by)
            ON CONFLICT (employee_id) DO UPDATE SET
              person_external_id = EXCLUDED.person_external_id,
              cedula = EXCLUDED.cedula,
              notes = EXCLUDED.notes,
              linked_by = EXCLUDED.linked_by,
              linked_at = NOW()
            """
        ),
        {
            "ext": ext,
            "eid": str(emp_uuid),
            "cedula": cedula,
            "notes": notes or "",
            "by": linked_by or "",
        },
    )
    db.commit()
    return {
        "employee_id": str(emp_uuid),
        "cedula": cedula,
        "full_name": f"{emp['first_name']} {emp['last_name']}".strip(),
        "person_external_id": ext,
        "linked": True,
    }


def unlink_person_from_employee(db: Session, *, employee_id: str) -> dict[str, Any]:
    try:
        emp_uuid = uuid.UUID(str(employee_id))
    except ValueError as exc:
        raise ValueError("employee_id inválido") from exc
    row = db.execute(
        text(
            """
            DELETE FROM biometrico.person_links
            WHERE employee_id = :eid
            RETURNING person_external_id
            """
        ),
        {"eid": str(emp_uuid)},
    ).first()
    db.commit()
    if not row:
        raise ValueError("No había vínculo para este empleado")
    return {"employee_id": str(emp_uuid), "person_external_id": row[0], "linked": False}


def presence_report(
    db: Session,
    *,
    day: str,
    core_site_id: str,
    biometric_site_id: Optional[str] = None,
) -> dict[str, Any]:
    """Empleados activos de una sede GTH vs marcajes del día (vía person_links)."""
    try:
        site_uuid = uuid.UUID(str(core_site_id))
    except ValueError as exc:
        raise ValueError("core_site_id inválido") from exc

    bio_sites: list[str] = []
    if biometric_site_id and biometric_site_id.strip():
        bio_sites = [biometric_site_id.strip()]
    else:
        mapped = db.execute(
            text(
                """
                SELECT biometric_site_id FROM biometrico.site_map
                WHERE core_site_id = :sid
                """
            ),
            {"sid": str(site_uuid)},
        ).scalars().all()
        bio_sites = [str(x) for x in mapped if x]

    expected = db.execute(
        text(
            """
            SELECT e.id::text AS employee_id, e.cedula, e.first_name, e.last_name,
                   pl.person_external_id
            FROM hr.employees e
            LEFT JOIN biometrico.person_links pl ON pl.employee_id = e.id
            WHERE e.is_active IS TRUE AND e.site_id = :sid
            ORDER BY e.last_name, e.first_name
            """
        ),
        {"sid": str(site_uuid)},
    ).mappings().all()

    marked_ids: set[str] = set()
    if bio_sites:
        placeholders = ", ".join(f":s{i}" for i in range(len(bio_sites)))
        params_m: dict[str, Any] = {"day": day}
        for i, sid in enumerate(bio_sites):
            params_m[f"s{i}"] = sid
        rows = db.execute(
            text(
                f"""
                SELECT DISTINCT e.person_external_id
                FROM biometrico.events e
                WHERE e.site_id IN ({placeholders})
                  AND e.occurred_at::date = CAST(:day AS date)
                  AND e.success IS TRUE
                """
            ),
            params_m,
        ).scalars().all()
        marked_ids = {str(x) for x in rows if x}
    else:
        # Sin mapa de sede: marcajes globales del día (menos preciso; documentado)
        rows = db.execute(
            text(
                """
                SELECT DISTINCT e.person_external_id
                FROM biometrico.events e
                WHERE e.occurred_at::date = CAST(:day AS date)
                  AND e.success IS TRUE
                """
            ),
            {"day": day},
        ).scalars().all()
        marked_ids = {str(x) for x in rows if x}

    present = []
    absent_linked = []
    unlinked = []
    for e in expected:
        item = {
            "employee_id": e["employee_id"],
            "cedula": e["cedula"] or "",
            "full_name": f"{e['first_name']} {e['last_name']}".strip(),
            "person_external_id": e["person_external_id"],
        }
        if not e["person_external_id"]:
            unlinked.append(item)
        elif e["person_external_id"] in marked_ids:
            present.append(item)
        else:
            absent_linked.append(item)

    return {
        "date": day,
        "core_site_id": str(site_uuid),
        "biometric_site_ids": bio_sites,
        "site_map_missing": len(bio_sites) == 0,
        "expected_active": len(expected),
        "present": present,
        "absent": absent_linked,
        "unlinked_employees": unlinked,
        "counts": {
            "present": len(present),
            "absent": len(absent_linked),
            "unlinked": len(unlinked),
        },
    }
