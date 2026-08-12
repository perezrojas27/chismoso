"""
Contrato real edge → cloud: enroll / ingest / heartbeat.

Auth agente: Bearer agent_credential o header X-Agent-Token.
Enroll: X-Enrollment-Token o body.enrollment_token == ENROLLMENT_TOKEN.
NO expone lab/issue-enrollment público.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.config import Settings, get_settings
from shared.database import get_db
from shared.pg_events import ingest_events

router = APIRouter(prefix="/api/asistencia/v1", tags=["asistencia-ingest"])


class EnrollBody(BaseModel):
    enrollment_token: str = ""
    agent_version: str = ""
    hostname: str = ""
    site_id: str = ""
    site_code: str = ""


class IngestEvent(BaseModel):
    device_id: str
    external_event_id: str
    occurred_at: str
    person_external_id: str
    person_name: str = ""
    employee_code: str = ""
    department: str = ""
    event_type: str = "unknown"
    success: bool = True


class IngestBody(BaseModel):
    agent_version: str = ""
    events: list[IngestEvent] = Field(default_factory=list)


class HeartbeatBody(BaseModel):
    agent_version: str = ""
    devices: list[dict[str, Any]] = Field(default_factory=list)
    sync: dict[str, Any] = Field(default_factory=dict)


def _hash_credential(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_agent_token(
    authorization: str | None,
    x_agent_token: str | None,
) -> str:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token and x_agent_token:
        token = x_agent_token.strip()
    return token


def _require_agent(
    db: Session,
    site_id: str,
    authorization: str | None,
    x_agent_token: str | None,
) -> dict[str, Any]:
    token = _extract_agent_token(authorization, x_agent_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial de agente requerida",
        )
    row = db.execute(
        text(
            """
            SELECT id, site_id, site_code, hostname, agent_version, revoked_at
            FROM biometrico.agents
            WHERE credential_hash = :ch
            LIMIT 1
            """
        ),
        {"ch": _hash_credential(token)},
    ).mappings().first()
    if not row or row.get("revoked_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial de agente inválida",
        )
    if str(row["site_id"]) != str(site_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credencial no corresponde a esta sede",
        )
    return dict(row)


def _resolve_enrollment_token(
    body_token: str,
    x_enrollment_token: str | None,
    settings: Settings,
) -> None:
    expected = (settings.enrollment_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ENROLLMENT_TOKEN no configurado en cloud",
        )
    provided = (x_enrollment_token or body_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="enrollment_token inválido",
        )


@router.post("/agents/enroll")
def enroll(
    body: EnrollBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_enrollment_token: str | None = Header(default=None, alias="X-Enrollment-Token"),
) -> dict:
    _resolve_enrollment_token(body.enrollment_token, x_enrollment_token, settings)

    site_code = (body.site_code or body.hostname or settings.site_code or "default").strip()
    site_id = (body.site_id or "").strip()

    if not site_id and site_code:
        existing = db.execute(
            text(
                """
                SELECT site_id FROM biometrico.agents
                WHERE site_code = :code AND revoked_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"code": site_code},
        ).scalar()
        if existing:
            site_id = str(existing)

    if not site_id:
        site_id = str(uuid.uuid4())

    credential = f"agent-{secrets.token_hex(24)}"
    credential_hash = _hash_credential(credential)
    agent_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            UPDATE biometrico.agents
            SET revoked_at = NOW()
            WHERE site_id = :site_id AND revoked_at IS NULL
            """
        ),
        {"site_id": site_id},
    )
    db.execute(
        text(
            """
            INSERT INTO biometrico.agents (
                id, credential_hash, site_id, site_code, hostname,
                agent_version, last_heartbeat_at, created_at
            ) VALUES (
                :id, :ch, :site_id, :site_code, :hostname,
                :agent_version, NULL, NOW()
            )
            """
        ),
        {
            "id": agent_id,
            "ch": credential_hash,
            "site_id": site_id,
            "site_code": site_code,
            "hostname": (body.hostname or "").strip(),
            "agent_version": (body.agent_version or "").strip(),
        },
    )
    db.commit()

    return {
        "site_id": site_id,
        "site_code": site_code,
        "agent_credential": credential,
        "ingest_url": f"/api/asistencia/v1/sites/{site_id}/ingest",
        "enrolled_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "hostname": body.hostname,
        "agent_version": body.agent_version,
    }


@router.post("/sites/{site_id}/ingest")
def ingest(
    site_id: str,
    body: IngestBody,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict:
    _require_agent(db, site_id, authorization, x_agent_token)

    accepted: list[str] = []
    duplicates: list[str] = []
    rejected: list[str] = []
    to_insert: list[dict[str, Any]] = []

    for ev in body.events:
        ext = (ev.external_event_id or "").strip()
        if not ext or not (ev.device_id or "").strip() or not (ev.person_external_id or "").strip():
            rejected.append(ext or "(empty)")
            continue
        to_insert.append(ev.model_dump())

    if to_insert:
        # Prefetch existentes por (device_id, external_event_id)
        for ev in to_insert:
            ext = ev["external_event_id"].strip()
            device_id = ev["device_id"].strip()
            exists = db.execute(
                text(
                    """
                    SELECT 1 FROM biometrico.events
                    WHERE site_id = :site_id
                      AND device_id = :device_id
                      AND external_event_id = :ext
                    LIMIT 1
                    """
                ),
                {"site_id": site_id, "device_id": device_id, "ext": ext},
            ).scalar()
            if exists:
                duplicates.append(ext)
            else:
                result = ingest_events(db, site_id, [ev])
                if result.get("inserted"):
                    accepted.append(ext)
                else:
                    duplicates.append(ext)

    if body.agent_version:
        db.execute(
            text(
                """
                UPDATE biometrico.agents
                SET agent_version = :ver
                WHERE site_id = :site_id AND revoked_at IS NULL
                """
            ),
            {"ver": body.agent_version.strip(), "site_id": site_id},
        )
        db.commit()

    return {
        "ok": True,
        "site_id": site_id,
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
    }


@router.post("/sites/{site_id}/heartbeat")
def heartbeat(
    site_id: str,
    body: HeartbeatBody,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict:
    agent = _require_agent(db, site_id, authorization, x_agent_token)
    now = datetime.now(timezone.utc)

    db.execute(
        text(
            """
            UPDATE biometrico.agents
            SET last_heartbeat_at = :now,
                agent_version = COALESCE(NULLIF(:ver, ''), agent_version)
            WHERE id = :id
            """
        ),
        {
            "now": now,
            "ver": (body.agent_version or "").strip(),
            "id": str(agent["id"]),
        },
    )

    for dev in body.devices:
        device_id = str(dev.get("device_id") or "").strip()
        if not device_id:
            continue
        last_event_at = dev.get("last_event_at")
        parsed_last = None
        if last_event_at:
            try:
                raw = str(last_event_at).replace("Z", "+00:00")
                parsed_last = datetime.fromisoformat(raw)
            except ValueError:
                parsed_last = None
        meta = {
            k: v
            for k, v in dev.items()
            if k not in ("device_id", "status", "host", "last_event_at")
        }
        db.execute(
            text(
                """
                INSERT INTO biometrico.agent_devices (
                    id, site_id, agent_id, device_id, status, host,
                    last_event_at, last_seen_at, meta
                ) VALUES (
                    :id, :site_id, :agent_id, :device_id, :status, :host,
                    :last_event_at, :now, CAST(:meta AS jsonb)
                )
                ON CONFLICT (site_id, device_id) DO UPDATE SET
                    agent_id = EXCLUDED.agent_id,
                    status = EXCLUDED.status,
                    host = EXCLUDED.host,
                    last_event_at = COALESCE(
                        EXCLUDED.last_event_at,
                        biometrico.agent_devices.last_event_at
                    ),
                    last_seen_at = EXCLUDED.last_seen_at,
                    meta = EXCLUDED.meta
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "site_id": site_id,
                "agent_id": str(agent["id"]),
                "device_id": device_id,
                "status": str(dev.get("status") or "unknown"),
                "host": str(dev.get("host") or ""),
                "last_event_at": parsed_last,
                "now": now,
                "meta": json.dumps(meta),
            },
        )

    reported_device_ids = [
        str(dev.get("device_id") or "").strip()
        for dev in body.devices
        if str(dev.get("device_id") or "").strip()
    ]
    if reported_device_ids:
        db.execute(
            text(
                """
                DELETE FROM biometrico.agent_devices
                WHERE site_id = :site_id
                  AND device_id != ALL(:reported)
                """
            ),
            {"site_id": site_id, "reported": reported_device_ids},
        )
    else:
        db.execute(
            text(
                """
                DELETE FROM biometrico.agent_devices
                WHERE site_id = :site_id
                """
            ),
            {"site_id": site_id},
        )

    db.commit()
    return {
        "ok": True,
        "site_id": site_id,
        "received_at": now.replace(microsecond=0).isoformat(),
        "devices_reported": len(body.devices),
        "sync": body.sync,
        "agent_version": body.agent_version,
    }
