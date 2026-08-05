"""
Generación de reportes de negocio a partir de AccessEvent limpios.

Reporte 1 — Asistencia: primera y última marca por empleado y día.
Reporte 2 — Comedor: presencia ≤ cutoff (09:00), orden de llegada, una fila por empleado.
           Las excepciones GTH permiten incluir llegadas posteriores al corte.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, time

from shared.models.events import AccessEvent
from shared.models.reports import (
    AttendanceReport,
    AttendanceRow,
    CafeteriaEmployee,
    CafeteriaReport,
)
from cloud_app.services.cafeteria_exceptions import CafeteriaException
from shared.services.name_format import format_employee_name


class ReportGenerator:
    def __init__(
        self,
        cafeteria_cutoff: time = time(9, 0, 0),
        cafeteria_exceptions: dict[str, CafeteriaException] | None = None,
    ) -> None:
        self.cafeteria_cutoff = cafeteria_cutoff
        self.cafeteria_exceptions = cafeteria_exceptions or {}

    def attendance_report(
        self,
        events: list[AccessEvent],
        from_date: date,
        to_date: date,
    ) -> AttendanceReport:
        by_day_employee: dict[tuple[date, str], list[AccessEvent]] = defaultdict(list)
        names: dict[str, str] = {}
        departments: dict[str, str] = {}

        for event in events:
            day = event.timestamp.date()
            if day < from_date or day > to_date:
                continue
            key = (day, event.employee_id)
            by_day_employee[key].append(event)
            names[event.employee_id] = format_employee_name(event.employee_name)
            if event.department:
                departments[event.employee_id] = event.department

        rows: list[AttendanceRow] = []
        for (day, emp_id), marks in by_day_employee.items():
            marks_sorted = sorted(marks, key=lambda m: m.timestamp)
            first = marks_sorted[0].timestamp
            last = marks_sorted[-1].timestamp
            rows.append(
                AttendanceRow(
                    date=day,
                    employee_id=emp_id,
                    employee_name=names.get(emp_id, emp_id),
                    department=departments.get(emp_id, marks_sorted[0].department),
                    first_seen_at=first,
                    last_seen_at=None if first == last else last,
                )
            )

        # Por fecha, luego por hora de llegada (temprano → tarde). La salida no afecta el orden.
        rows.sort(
            key=lambda r: (
                r.date,
                r.first_seen_at,
                r.employee_name.casefold(),
                r.employee_id,
            )
        )

        return AttendanceReport(from_date=from_date, to_date=to_date, rows=rows)

    def cafeteria_report(self, events: list[AccessEvent], report_date: date) -> CafeteriaReport:
        """
        Incluye:
        - marcas ≤ cutoff, o
        - marcas del día con permiso GTH (excepción), aunque sean después del corte.
        """
        first_arrival: dict[str, AccessEvent] = {}
        via_exception: set[str] = set()

        for event in events:
            if event.timestamp.date() != report_date:
                continue
            on_time = event.timestamp.time() <= self.cafeteria_cutoff
            allowed = event.employee_id in self.cafeteria_exceptions
            if not on_time and not allowed:
                continue
            existing = first_arrival.get(event.employee_id)
            if existing is None or event.timestamp < existing.timestamp:
                first_arrival[event.employee_id] = event

        for emp_id, event in first_arrival.items():
            if event.timestamp.time() > self.cafeteria_cutoff and emp_id in self.cafeteria_exceptions:
                via_exception.add(emp_id)

        ordered = sorted(first_arrival.values(), key=lambda e: e.timestamp)
        employees: list[CafeteriaEmployee] = []
        for e in ordered:
            exc = self.cafeteria_exceptions.get(e.employee_id)
            has_exc = e.employee_id in via_exception
            employees.append(
                CafeteriaEmployee(
                    employee_id=e.employee_id,
                    employee_name=format_employee_name(e.employee_name),
                    department=e.department,
                    marked_time=e.timestamp,
                    observation=exc.observation_label() if has_exc and exc else "",
                    has_exception=has_exc,
                )
            )

        return CafeteriaReport(
            date=report_date,
            cutoff=self.cafeteria_cutoff.strftime("%H:%M:%S"),
            headcount=len(employees),
            employees=employees,
            exceptions_count=sum(1 for e in employees if e.has_exception),
        )
