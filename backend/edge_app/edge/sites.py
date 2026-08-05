"""
Registro de sedes (sites) — multi-sede ready.

Aunque hoy haya una sola oficina, todo dispositivo y evento lleva site_id.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sites.json"
_lock = threading.Lock()


class Site(BaseModel):
    id: str
    code: str
    name: str
    timezone: str = "America/Caracas"
    status: str = "active"  # pending | active | disabled
    cafeteria_cutoff: str = "09:00:00"
    cafeteria_late_end: str = "11:00:00"
    created_at: str = ""
    updated_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_site(code: str = "oficina_central", name: str = "Torre Sindoni (oficina central)") -> Site:
    now = _now_iso()
    return Site(
        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"albatros.site.{code}")),
        code=code,
        name=name,
        timezone="America/Caracas",
        status="active",
        cafeteria_cutoff="09:00:00",
        cafeteria_late_end="11:00:00",
        created_at=now,
        updated_at=now,
    )


class SiteRegistry:
    def __init__(self, path: Path = _DATA_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([_default_site()])

    def _read(self) -> list[Site]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [_default_site()]
        items: list[Site] = []
        for row in raw:
            try:
                items.append(Site.model_validate(row))
            except Exception:
                continue
        return items or [_default_site()]

    def _write(self, items: list[Site]) -> None:
        payload = [i.model_dump(mode="json") for i in items]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_sites(self) -> list[Site]:
        with _lock:
            return self._read()

    def get_by_id(self, site_id: str) -> Site | None:
        sid = (site_id or "").strip()
        for s in self.list_sites():
            if s.id == sid:
                return s
        return None

    def get_by_code(self, code: str) -> Site | None:
        c = (code or "").strip().lower()
        for s in self.list_sites():
            if s.code.lower() == c:
                return s
        return None

    def ensure_default(self, code: str, name: str) -> Site:
        with _lock:
            items = self._read()
            for s in items:
                if s.code.lower() == code.lower():
                    return s
            site = _default_site(code=code, name=name)
            items.append(site)
            self._write(items)
            return site

    def upsert(self, site: Site) -> Site:
        with _lock:
            items = self._read()
            site.updated_at = _now_iso()
            out: list[Site] = []
            found = False
            for s in items:
                if s.id == site.id or s.code.lower() == site.code.lower():
                    out.append(site)
                    found = True
                else:
                    out.append(s)
            if not found:
                if not site.created_at:
                    site.created_at = site.updated_at
                out.append(site)
            self._write(out)
            return site


_registry: SiteRegistry | None = None


def get_site_registry() -> SiteRegistry:
    global _registry
    if _registry is None:
        _registry = SiteRegistry()
    return _registry
