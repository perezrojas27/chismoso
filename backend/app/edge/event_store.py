"""
Store local de eventos normalizados (SQLite).

Reportes cloud-app leen desde aquí; el edge escribe vía sync ISAPI.
Idempotencia: UNIQUE(site_id, device_id, external_event_id).
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from app.models.events import AccessEvent
from app.services.hikvision_connector import resolve_department, RawAccessEvent

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "events.sqlite3"
_lock = threading.Lock()


def make_external_event_id(
    device_id: str,
    occurred_at: datetime,
    person_external_id: str,
    *,
    major: int | None = None,
    minor: int | None = None,
) -> str:
    """Id estable para idempotencia edge→cloud."""
    stamp = occurred_at.strftime("%Y%m%dT%H%M%S")
    seed = f"{device_id}|{stamp}|{person_external_id}|{major}|{minor}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"{device_id}:{stamp}:{person_external_id}:{digest}"


class EventStore:
    def __init__(self, path: Path = _DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with _lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        external_event_id TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        person_external_id TEXT NOT NULL,
                        person_name TEXT DEFAULT '',
                        employee_code TEXT DEFAULT '',
                        department TEXT DEFAULT '',
                        event_type TEXT DEFAULT 'unknown',
                        success INTEGER DEFAULT 1,
                        ingested INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        UNIQUE(site_id, device_id, external_event_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_events_range
                        ON events(site_id, occurred_at);
                    CREATE TABLE IF NOT EXISTS sync_cursors (
                        device_id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        last_sync_at TEXT,
                        last_event_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS outbox (
                        id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        attempts INTEGER DEFAULT 0,
                        last_error TEXT DEFAULT '',
                        UNIQUE(event_id)
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def upsert_raw_events(
        self,
        site_id: str,
        raw_events: list[RawAccessEvent],
    ) -> dict[str, int]:
        """Inserta eventos crudos normalizados. Retorna contadores."""
        inserted = 0
        duplicated = 0
        now = datetime.now().replace(microsecond=0).isoformat()
        with _lock:
            conn = self._connect()
            try:
                for raw in raw_events:
                    if raw.timestamp is None or not (raw.employee_id or "").strip():
                        continue
                    device_id = (raw.device_id or "").strip() or "UNKNOWN"
                    emp = raw.employee_id.strip()
                    external_id = make_external_event_id(
                        device_id,
                        raw.timestamp,
                        emp,
                        major=raw.major,
                        minor=raw.minor,
                    )
                    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, external_id))
                    try:
                        conn.execute(
                            """
                            INSERT INTO events (
                                id, site_id, device_id, external_event_id, occurred_at,
                                person_external_id, person_name, employee_code, department,
                                event_type, success, ingested, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                            """,
                            (
                                event_id,
                                site_id,
                                device_id,
                                external_id,
                                raw.timestamp.isoformat(sep="T", timespec="seconds"),
                                emp,
                                (raw.employee_name or "").strip(),
                                emp,  # employee_code alineable a GTH cuando exista mapeo
                                (raw.department or "").strip(),
                                "unknown",
                                1 if raw.success else 0,
                                now,
                            ),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO outbox (id, event_id, created_at) VALUES (?, ?, ?)",
                            (str(uuid.uuid4()), event_id, now),
                        )
                        inserted += 1
                    except sqlite3.IntegrityError:
                        duplicated += 1
                conn.commit()
            finally:
                conn.close()
        return {"inserted": inserted, "duplicated": duplicated, "total": inserted + duplicated}

    def set_cursor(self, site_id: str, device_id: str, last_event_at: datetime | None) -> None:
        now = datetime.now().replace(microsecond=0).isoformat()
        with _lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sync_cursors (device_id, site_id, last_sync_at, last_event_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        site_id=excluded.site_id,
                        last_sync_at=excluded.last_sync_at,
                        last_event_at=COALESCE(excluded.last_event_at, sync_cursors.last_event_at)
                    """,
                    (
                        device_id,
                        site_id,
                        now,
                        last_event_at.isoformat(sep="T", timespec="seconds") if last_event_at else None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def get_cursor(self, device_id: str) -> dict | None:
        with _lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM sync_cursors WHERE device_id = ?",
                    (device_id,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def query_access_events(
        self,
        site_id: str,
        from_date: date,
        to_date: date,
    ) -> list[AccessEvent]:
        start = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)
        end = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59)
        with _lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT person_external_id, person_name, department, occurred_at, device_id
                    FROM events
                    WHERE site_id = ?
                      AND success = 1
                      AND occurred_at >= ?
                      AND occurred_at <= ?
                    ORDER BY occurred_at ASC
                    """,
                    (site_id, start.isoformat(sep="T"), end.isoformat(sep="T")),
                ).fetchall()
            finally:
                conn.close()

        events: list[AccessEvent] = []
        for row in rows:
            emp_id = row["person_external_id"]
            emp_name = row["person_name"] or row["person_external_id"]
            dept = (row["department"] or "").strip()
            if not dept:
                dept = resolve_department(emp_id, emp_name)
            events.append(
                AccessEvent(
                    employee_id=emp_id,
                    employee_name=emp_name,
                    department=dept,
                    timestamp=datetime.fromisoformat(row["occurred_at"]),
                    device_id=row["device_id"],
                )
            )
        return events

    def pending_outbox(self, limit: int = 200) -> list[dict]:
        with _lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT e.*, o.id AS outbox_id, o.attempts
                    FROM outbox o
                    JOIN events e ON e.id = o.event_id
                    WHERE e.ingested = 0
                    ORDER BY e.occurred_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def mark_ingested(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        with _lock:
            conn = self._connect()
            try:
                conn.executemany(
                    "UPDATE events SET ingested = 1 WHERE id = ?",
                    [(eid,) for eid in event_ids],
                )
                conn.executemany(
                    "DELETE FROM outbox WHERE event_id = ?",
                    [(eid,) for eid in event_ids],
                )
                conn.commit()
            finally:
                conn.close()

    def stats(self, site_id: str | None = None) -> dict:
        with _lock:
            conn = self._connect()
            try:
                if site_id:
                    total = conn.execute(
                        "SELECT COUNT(*) FROM events WHERE site_id = ?", (site_id,)
                    ).fetchone()[0]
                    pending = conn.execute(
                        """
                        SELECT COUNT(*) FROM outbox o
                        JOIN events e ON e.id = o.event_id
                        WHERE e.site_id = ? AND e.ingested = 0
                        """,
                        (site_id,),
                    ).fetchone()[0]
                else:
                    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                    pending = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
                return {"events_total": total, "outbox_pending": pending}
            finally:
                conn.close()


_store: EventStore | None = None


def get_event_store() -> EventStore:
    global _store
    if _store is None:
        _store = EventStore()
    return _store
