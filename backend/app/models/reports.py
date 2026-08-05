from datetime import date, datetime

from pydantic import BaseModel, Field


class AttendanceRow(BaseModel):
    date: date
    employee_id: str
    employee_name: str
    department: str = ""
    first_seen_at: datetime
    last_seen_at: datetime | None = None


class AttendanceReport(BaseModel):
    from_date: date
    to_date: date
    rows: list[AttendanceRow] = Field(default_factory=list)


class CafeteriaEmployee(BaseModel):
    employee_id: str
    employee_name: str
    department: str = ""
    # Usado solo para orden de llegada; la UI/PDF no lo muestran.
    marked_time: datetime
    observation: str = ""
    has_exception: bool = False


class CafeteriaReport(BaseModel):
    date: date
    cutoff: str
    # Conte total de personas (expuesto como headcount en JSON; UI/PDF dicen "Total")
    headcount: int
    employees: list[CafeteriaEmployee] = Field(default_factory=list)
    exceptions_count: int = 0
