"""
Persistencia mínima del agente edge (site_id + agent_credential).

Sobrevive reinicios del contenedor vía volumen /data.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    root = Path(os.environ.get("EDGE_DATA_DIR", "/data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "edge_state.json"


def load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("No se pudo leer edge_state: %s", exc)
        return {}


def save_state(data: dict[str, Any]) -> None:
    path = _state_path()
    merged = load_state()
    merged.update({k: v for k, v in data.items() if v is not None})
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
