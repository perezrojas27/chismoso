"""
Mock del contrato INTEGRADO (enroll / ingest / heartbeat).

Permite desarrollar el agente edge sin cloud real.
Rutas alineadas a la guía: /api/asistencia/v1/...
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from edge_app.edge.sites import Site, get_site_registry

router = APIRouter(prefix="/api/asistencia/v1", tags=["cloud-mock"])

# Estado en memoria del mock (lab local)
_ENROLLMENT_TOKENS: dict[str, str] = {}  # token → site_code
_AGENT_CREDS: dict[str, str] = {}  # credential → site_id
_INGESTED: set[str] = set()  # external_event_id


class EnrollBody(BaseModel):
    enrollment_token: str
    agent_version: str = ""
    hostname: str = ""


class IngestEvent(BaseModel):
    device_id: str
    external_event_id: str
    occurred_at: str
    person_external_id: str
    person_name: str = ""
    employee_code: str = ""
    event_type: str = "unknown"
    success: bool = True


class IngestBody(BaseModel):
    agent_version: str = ""
    events: list[IngestEvent] = Field(default_factory=list)


class HeartbeatBody(BaseModel):
    agent_version: str = ""
    devices: list[dict] = Field(default_factory=list)
    sync: dict = Field(default_factory=dict)


def _require_agent(authorization: str | None, x_agent_token: str | None) -> str:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token and x_agent_token:
        token = x_agent_token.strip()
    if not token:
        # Lab: permitir sin cred si no hay ninguna registrada
        if not _AGENT_CREDS:
            return ""
        raise HTTPException(status_code=401, detail="Credencial de agente requerida")
    if _AGENT_CREDS and token not in _AGENT_CREDS:
        raise HTTPException(status_code=401, detail="Credencial de agente inválida")
    return token


@router.post("/lab/issue-enrollment")
async def issue_enrollment(site_code: str = "oficina_central", site_name: str = "") -> dict:
    """Solo lab: genera enrollment_token para una sede."""
    registry = get_site_registry()
    site = registry.ensure_default(site_code, site_name or site_code.replace("_", " ").title())
    token = f"enroll-{uuid.uuid4().hex[:16]}"
    _ENROLLMENT_TOKENS[token] = site.code
    return {
        "enrollment_token": token,
        "site_id": site.id,
        "site_code": site.code,
        "expires_hint": "lab-only (sin caducidad en mock)",
    }


@router.post("/agents/enroll")
async def enroll(body: EnrollBody) -> dict:
    site_code = _ENROLLMENT_TOKENS.get(body.enrollment_token.strip())
    if not site_code:
        # Acepta cualquier token en lab si prefijo enroll- o settings
        if body.enrollment_token.startswith("enroll-") or body.enrollment_token == "lab-token":
            site_code = "oficina_central"
        else:
            raise HTTPException(status_code=400, detail="enrollment_token inválido")

    registry = get_site_registry()
    site = registry.ensure_default(site_code, site_code.replace("_", " ").title())
    if site.status == "pending":
        site = Site(**{**site.model_dump(), "status": "active"})
        registry.upsert(site)

    cred = f"agent-{uuid.uuid4().hex}"
    _AGENT_CREDS[cred] = site.id
    return {
        "site_id": site.id,
        "site_code": site.code,
        "agent_credential": cred,
        "ingest_url": f"/api/asistencia/v1/sites/{site.id}/ingest",
        "enrolled_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "hostname": body.hostname,
        "agent_version": body.agent_version,
    }


@router.post("/sites/{site_id}/ingest")
async def ingest(
    site_id: str,
    body: IngestBody,
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict:
    _require_agent(authorization, x_agent_token)
    accepted: list[str] = []
    duplicates: list[str] = []
    rejected: list[str] = []
    for ev in body.events:
        ext = (ev.external_event_id or "").strip()
        if not ext or not ev.device_id or not ev.person_external_id:
            rejected.append(ext or "(empty)")
            continue
        if ext in _INGESTED:
            duplicates.append(ext)
            continue
        _INGESTED.add(ext)
        accepted.append(ext)
    return {
        "ok": True,
        "site_id": site_id,
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
    }


@router.post("/sites/{site_id}/heartbeat")
async def heartbeat(
    site_id: str,
    body: HeartbeatBody,
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict:
    _require_agent(authorization, x_agent_token)
    return {
        "ok": True,
        "site_id": site_id,
        "received_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "devices_reported": len(body.devices),
        "sync": body.sync,
        "agent_version": body.agent_version,
    }


@router.post("/sites/{site_id}/devices/upsert")
async def devices_upsert(
    site_id: str,
    body: dict,
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict:
    _require_agent(authorization, x_agent_token)
    devices = body.get("devices") or []
    return {"ok": True, "site_id": site_id, "upserted": len(devices)}
