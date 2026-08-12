"""Credenciales de la consola del agente edge (persistidas en EDGE_DATA_DIR)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()


def _data_dir() -> Path:
    raw = (os.environ.get("EDGE_DATA_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data"


def auth_path() -> Path:
    return _data_dir() / "console_auth.json"


def load_console_auth() -> dict[str, str] | None:
    path = auth_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    user = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    if not password:
        return None
    return {"username": user or "admin", "password": password}


def save_console_auth(username: str, password: str) -> None:
    path = auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "username": (username or "admin").strip() or "admin",
        "password": password,
    }
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
