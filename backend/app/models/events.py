from datetime import datetime

from pydantic import BaseModel, Field


class AccessEvent(BaseModel):
    """Evento de acceso normalizado (post-limpieza)."""

    employee_id: str
    employee_name: str
    department: str = ""
    timestamp: datetime
    device_id: str


class RawAccessEvent(BaseModel):
    """Evento crudo proveniente del conector (mock o ISAPI)."""

    employee_id: str = Field(default="")
    employee_name: str = Field(default="")
    department: str = Field(default="")
    timestamp: datetime | None = None
    device_id: str = Field(default="")
    # major/minor típicos de AcsEvent; autenticación exitosa ≈ major=5
    major: int | None = None
    minor: int | None = None
    success: bool = True
