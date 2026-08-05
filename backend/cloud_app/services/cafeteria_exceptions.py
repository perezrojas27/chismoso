"""Excepciones de comedor registradas por GTH (llegada autorizada después del corte)."""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "cafeteria_exceptions.json"
_lock = threading.Lock()


class CafeteriaException(BaseModel):
    employee_id: str
    date: date
    reason: str = Field(min_length=1, max_length=200)
    registered_by: str = "GTH"

    def observation_label(self) -> str:
        note = (self.reason or "").strip()
        return f"Permiso GTH: {note}" if note else "Permiso GTH"


class CafeteriaExceptionCreate(BaseModel):
    employee_id: str
    date: date
    reason: str = Field(min_length=1, max_length=200)
    registered_by: str = "GTH"


class CafeteriaExceptionStore:
    def __init__(self, path: Path = _DATA_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[CafeteriaException]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items: list[CafeteriaException] = []
        for row in raw:
            try:
                items.append(CafeteriaException.model_validate(row))
            except Exception:
                continue
        return items

    def _write(self, items: list[CafeteriaException]) -> None:
        payload = [i.model_dump(mode="json") for i in items]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_for_date(self, day: date) -> list[CafeteriaException]:
        with _lock:
            return [e for e in self._read() if e.date == day]

    def index_for_date(self, day: date) -> dict[str, CafeteriaException]:
        return {e.employee_id: e for e in self.list_for_date(day)}

    def upsert(self, item: CafeteriaException) -> CafeteriaException:
        with _lock:
            items = self._read()
            items = [e for e in items if not (e.employee_id == item.employee_id and e.date == item.date)]
            items.append(item)
            self._write(items)
            return item

    def delete(self, employee_id: str, day: date) -> bool:
        with _lock:
            items = self._read()
            next_items = [e for e in items if not (e.employee_id == employee_id and e.date == day)]
            if len(next_items) == len(items):
                return False
            self._write(next_items)
            return True


_store: CafeteriaExceptionStore | None = None


def get_cafeteria_exception_store() -> CafeteriaExceptionStore:
    global _store
    if _store is None:
        _store = CafeteriaExceptionStore()
    return _store
