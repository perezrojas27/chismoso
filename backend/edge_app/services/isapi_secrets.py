"""Credenciales ISAPI persistidas en el volumen del edge (no en git)."""

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


def secrets_path() -> Path:
    return _data_dir() / "isapi_credentials.json"


def load_isapi_credentials() -> dict[str, str] | None:
    path = secrets_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    user = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    if not user or not password:
        return None
    return {"username": user, "password": password}


def save_isapi_credentials(username: str, password: str) -> None:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": username.strip(), "password": password}
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
