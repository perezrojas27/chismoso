"""Identidad de sede del agente edge (SITE_CODE / SITE_NAME)."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

_lock = threading.Lock()
_SITE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,62}$")


def _data_dir(explicit: str | Path | None = None) -> Path:
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip())
    raw = (os.environ.get("EDGE_DATA_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data"


def identity_path(data_dir: str | Path | None = None) -> Path:
    return _data_dir(data_dir) / "site_identity.json"


def validate_site_code(code: str) -> str:
    cleaned = (code or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not _SITE_CODE_RE.match(cleaned):
        raise ValueError(
            "Código de sede inválido: use 2–63 caracteres [a-z0-9_], "
            "empezando por letra o dígito (ej. oficina_central, valencia_norte)."
        )
    return cleaned


def load_site_identity(data_dir: str | Path | None = None) -> dict[str, str] | None:
    path = identity_path(data_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    code = str(raw.get("site_code") or "").strip()
    name = str(raw.get("site_name") or "").strip()
    if not code:
        return None
    try:
        code = validate_site_code(code)
    except ValueError:
        return None
    return {
        "site_code": code,
        "site_name": name or code.replace("_", " ").title(),
    }


def save_site_identity(
    site_code: str,
    site_name: str,
    data_dir: str | Path | None = None,
) -> Path:
    code = validate_site_code(site_code)
    name = (site_name or "").strip() or code.replace("_", " ").title()
    path = identity_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"site_code": code, "site_name": name}
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    loaded = load_site_identity(data_dir)
    if not loaded or loaded.get("site_code") != code:
        raise OSError(f"No se pudo verificar site_identity en {path}")
    return path


def sync_env_site_identity(
    site_code: str,
    site_name: str,
    *,
    env_path: Path | None = None,
) -> bool:
    """Actualiza SITE_CODE / SITE_NAME en backend/.env."""
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

    code = site_code.replace("\n", "").replace("\r", "")
    name = site_name.replace("\n", "").replace("\r", "")
    updated = _set("SITE_CODE", code, text)
    updated = _set("SITE_NAME", name, updated)
    if updated == text:
        return True
    try:
        path.write_text(updated, encoding="utf-8")
        return True
    except OSError:
        return False
