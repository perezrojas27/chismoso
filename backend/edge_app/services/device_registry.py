"""Registro de dispositivos Hikvision administrables desde la UI (admin/TI)."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from shared.config import HikvisionDevice

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "hikvision_devices.json"
_lock = threading.Lock()

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
_HOST_RE = re.compile(
    r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9](?:[A-Za-z0-9.-]{0,61}[A-Za-z0-9])?)$"
)

# Ubicaciones conocidas por host (sede física)
_DEFAULT_LOCATIONS_BY_HOST: dict[str, str] = {
    "192.168.10.200": "Torre Sindoni Ascensores Pequeños",
    "192.168.10.201": "Torre Sindoni Ascensores Pequeños",
}

# Compat: IDs históricos del .env
_DEFAULT_LOCATIONS_BY_ID: dict[str, str] = {
    "PRINCIPAL": "Torre Sindoni Ascensores Pequeños",
    "SECUNDARIA": "Torre Sindoni Ascensores Pequeños",
}


def resolve_device_location(
    device_id: str,
    managed_location: str | None = None,
    *,
    host: str | None = None,
) -> str:
    """Prioriza ubicación del registro UI; luego host; luego ID legacy."""
    if (managed_location or "").strip():
        return managed_location.strip()
    host_key = (host or "").strip()
    if host_key and host_key in _DEFAULT_LOCATIONS_BY_HOST:
        return _DEFAULT_LOCATIONS_BY_HOST[host_key]
    return _DEFAULT_LOCATIONS_BY_ID.get((device_id or "").strip().upper(), "")


def device_id_from_host(host: str) -> str:
    """ID interno estable a partir del host (no se muestra en UI)."""
    cleaned = (host or "").strip().replace(".", "-")
    return f"BIO-{cleaned}"[:32]


class ManagedDevice(BaseModel):
    device_id: str = Field(min_length=2, max_length=32)
    host: str = Field(min_length=3, max_length=120)
    port: int = Field(default=80, ge=1, le=65535)
    location: str = Field(default="", max_length=120)
    site_id: str = Field(default="", max_length=64)

    @field_validator("device_id")
    @classmethod
    def _id_ok(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not _ID_RE.match(cleaned):
            raise ValueError("ID inválido (2–32: letras, números, _ o -)")
        return cleaned

    @field_validator("host")
    @classmethod
    def _host_ok(cls, value: str) -> str:
        cleaned = value.strip()
        if not _HOST_RE.match(cleaned):
            raise ValueError("Host inválido (IP o nombre)")
        return cleaned

    @field_validator("location")
    @classmethod
    def _location_ok(cls, value: str) -> str:
        return (value or "").strip()

    def to_hikvision(self) -> HikvisionDevice:
        return HikvisionDevice(device_id=self.device_id, host=self.host, port=self.port)


class ManagedDeviceCreate(BaseModel):
    host: str
    port: int = 80
    location: str = ""
    device_id: str | None = None


class DeviceRegistry:
    def __init__(self, path: Path = _DATA_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[ManagedDevice]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items: list[ManagedDevice] = []
        for row in raw:
            try:
                items.append(ManagedDevice.model_validate(row))
            except Exception:
                continue
        return items

    def _write(self, items: list[ManagedDevice]) -> None:
        payload = [i.model_dump(mode="json") for i in items]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_devices(self) -> list[ManagedDevice]:
        with _lock:
            return self._read()

    def location_by_id(self) -> dict[str, str]:
        return {d.device_id: d.location for d in self.list_devices() if d.location}

    def upsert(self, item: ManagedDevice) -> ManagedDevice:
        with _lock:
            items = self._read()
            items = [d for d in items if d.device_id != item.device_id]
            items.append(item)
            items.sort(key=lambda d: d.device_id)
            self._write(items)
            return item

    def delete(self, device_id: str) -> bool:
        key = device_id.strip().upper()
        with _lock:
            items = self._read()
            next_items = [d for d in items if d.device_id != key]
            if len(next_items) == len(items):
                return False
            self._write(next_items)
            return True


_registry: DeviceRegistry | None = None


def get_device_registry() -> DeviceRegistry:
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry
