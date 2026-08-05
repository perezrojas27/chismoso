"""
Cliente HTTP del agente edge → INTEGRADO (enroll / ingest / heartbeat).

En local apunta al mock cloud del mismo backend si INTEGRADO_BASE_URL está vacío
o a la URL configurada.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

AGENT_VERSION = "1.1.0"


class CloudAgentClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        base = (settings.integrado_base_url or "").rstrip("/")
        # Mock local embebido
        self.base_url = base or "http://127.0.0.1:8003"
        self.timeout = settings.integrado_timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        cred = (self.settings.agent_credential or "").strip()
        if cred:
            headers["Authorization"] = f"Bearer {cred}"
            headers["X-Agent-Token"] = cred
        return headers

    async def enroll(self, enrollment_token: str, hostname: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/asistencia/v1/agents/enroll"
        payload = {
            "enrollment_token": enrollment_token,
            "agent_version": AGENT_VERSION,
            "hostname": hostname,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def ingest(self, site_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self.base_url}/api/asistencia/v1/sites/{site_id}/ingest"
        payload = {"agent_version": AGENT_VERSION, "events": events}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def heartbeat(self, site_id: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/api/asistencia/v1/sites/{site_id}/heartbeat"
        payload = {"agent_version": AGENT_VERSION, **body}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
