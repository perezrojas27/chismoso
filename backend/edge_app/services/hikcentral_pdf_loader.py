"""
Carga eventos desde el PDF «Tarjeta de registro de tiempo» de HikCentral.

Formato típico por fila (texto extraído):
  NOMBRE(S)
  APELLIDO(S)
  All Departments>DEPTO   (o solo «All Departments»)
  YYYY-MM-DD
  HH:MM;HH:MM;...
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from pypdf import PdfReader

from shared.models.events import RawAccessEvent

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(\d{2}:\d{2})(;\d{2}:\d{2})*$")
DEPT_PREFIX = "All Departments>"
DEPT_ROOT = "All Departments"


def _employee_id_for(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8].upper()
    return f"HC-{digest}"


def _normalize_department(raw: str) -> str:
    dept = " ".join((raw or "").split()).strip()
    if not dept or dept == DEPT_ROOT:
        return ""
    # PDF a veces rompe la Á de AERONÁUTICO
    dept = re.sub(r"AERON.UTICO", "AERONAUTICO", dept, flags=re.IGNORECASE)
    return dept.upper() if dept else dept


def _is_department_line(line: str) -> bool:
    return line == DEPT_ROOT or line.startswith(DEPT_PREFIX)


def parse_hikcentral_timecard_pdf(pdf_path: Path) -> list[dict]:
    """
    Devuelve registros planos:
      {employee_name, department, date, times: ["HH:MM", ...]}
    """
    reader = PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(ln.strip() for ln in text.splitlines() if ln.strip())

    try:
        start = lines.index("Registro") + 1
        lines = lines[start:]
    except ValueError:
        logger.warning("Encabezado 'Registro' no encontrado; se parsea todo el texto")

    records: list[dict] = []
    i = 0
    while i < len(lines):
        name_parts: list[str] = []
        while i < len(lines) and not _is_department_line(lines[i]) and not DATE_RE.match(lines[i]):
            name_parts.append(lines[i])
            i += 1
        if i >= len(lines):
            break

        dept_parts: list[str] = []
        if lines[i] == DEPT_ROOT:
            i += 1
        elif lines[i].startswith(DEPT_PREFIX):
            dept_parts.append(lines[i][len(DEPT_PREFIX) :].strip())
            i += 1
            while (
                i < len(lines)
                and not DATE_RE.match(lines[i])
                and not _is_department_line(lines[i])
                and not TIME_RE.match(lines[i])
            ):
                dept_parts.append(lines[i])
                i += 1

        if i >= len(lines) or not DATE_RE.match(lines[i]):
            logger.warning("Sincronización PDF fallida cerca de %s", lines[i : i + 4])
            break
        day = lines[i]
        i += 1
        if i >= len(lines) or not TIME_RE.match(lines[i]):
            logger.warning("Sin horarios tras fecha %s (%s)", day, name_parts)
            break
        times_raw = lines[i]
        i += 1

        name = " ".join(name_parts).strip()
        if not name:
            continue
        records.append(
            {
                "employee_name": name,
                "department": _normalize_department(" ".join(dept_parts)),
                "date": day,
                "times": times_raw.split(";"),
            }
        )

    return records


def records_to_raw_events(
    records: list[dict],
    *,
    device_id: str = "HIKCENTRAL-PDF",
) -> list[RawAccessEvent]:
    events: list[RawAccessEvent] = []
    for rec in records:
        name = rec["employee_name"]
        emp_id = _employee_id_for(name)
        department = rec.get("department") or ""
        day = date.fromisoformat(rec["date"])
        for t in rec.get("times") or []:
            hour, minute = map(int, t.split(":"))
            events.append(
                RawAccessEvent(
                    employee_id=emp_id,
                    employee_name=name,
                    department=department,
                    timestamp=datetime(day.year, day.month, day.day, hour, minute, 0),
                    device_id=device_id,
                    success=True,
                    major=5,
                    minor=75,
                )
            )
    events.sort(key=lambda e: (e.timestamp or datetime.min, e.employee_name))
    return events


def load_events_from_pdf(pdf_path: Path, *, device_id: str = "HIKCENTRAL-PDF") -> list[RawAccessEvent]:
    return records_to_raw_events(parse_hikcentral_timecard_pdf(pdf_path), device_id=device_id)


def load_events_from_json(json_path: Path) -> list[RawAccessEvent]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    device_id = payload.get("device_id") or "HIKCENTRAL-PDF"
    return records_to_raw_events(payload.get("records") or [], device_id=device_id)


def export_records_json(pdf_path: Path, out_path: Path, *, device_id: str = "HIKCENTRAL-PDF") -> dict:
    records = parse_hikcentral_timecard_pdf(pdf_path)
    payload = {
        "source": "hikcentral_timecard_pdf",
        "pdf": str(pdf_path),
        "device_id": device_id,
        "period": {
            "from": min((r["date"] for r in records), default=None),
            "to": max((r["date"] for r in records), default=None),
        },
        "people": len({r["employee_name"] for r in records}),
        "day_rows": len(records),
        "marks": sum(len(r["times"]) for r in records),
        "records": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
