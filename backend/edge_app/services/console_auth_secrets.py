"""Credenciales de la consola del agente edge (persistidas en EDGE_DATA_DIR)."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

_lock = threading.Lock()


def _data_dir(explicit: str | Path | None = None) -> Path:
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip())
    raw = (os.environ.get("EDGE_DATA_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data"


def auth_path(data_dir: str | Path | None = None) -> Path:
    return _data_dir(data_dir) / "console_auth.json"


def load_console_auth(data_dir: str | Path | None = None) -> dict[str, str] | None:
    path = auth_path(data_dir)
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


def save_console_auth(
    username: str,
    password: str,
    data_dir: str | Path | None = None,
) -> Path:
    path = auth_path(data_dir)
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
    # Verificar lectura inmediata
    loaded = load_console_auth(data_dir)
    if not loaded or loaded.get("password") != password:
        raise OSError(f"No se pudo verificar la clave guardada en {path}")
    return path


def sync_env_console_credentials(
    username: str,
    password: str,
    *,
    env_path: Path | None = None,
) -> bool:
    """Actualiza EDGE_ADMIN_USER/PASSWORD en backend/.env (sin tocar otros valores)."""
    path = env_path or (Path(__file__).resolve().parents[2] / ".env")
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    def _set(key: str, value: str, src: str) -> str:
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        line = f"{key}={value}"
        if pattern.search(src):
            return pattern.sub(line, src, count=1)
        return src.rstrip() + "\n" + line + "\n"

    # Escapar saltos en valores (no se esperan)
    user = (username or "admin").replace("\n", "").replace("\r", "")
    pwd = password.replace("\n", "").replace("\r", "")
    updated = _set("EDGE_ADMIN_USER", user, text)
    updated = _set("EDGE_ADMIN_PASSWORD", pwd, updated)
    if updated == text:
        return True
    try:
        path.write_text(updated, encoding="utf-8")
        return True
    except OSError:
        return False
