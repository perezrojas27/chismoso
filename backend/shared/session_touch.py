"""Idle + denylist vía core.touch_auth_session (misma BD albatros_core_db).

Copia ligera para microservicios (no importan el paquete IdP).
"""
from __future__ import annotations

import os

from fastapi import HTTPException, status
from sqlalchemy import text

AUTH_IDLE_TIMEOUT_MINUTES = int(os.getenv("AUTH_IDLE_TIMEOUT_MINUTES", "30") or "30")


def assert_auth_session_sync(db, payload: dict) -> None:
    jti = payload.get("jti") if isinstance(payload, dict) else None
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida; inicie sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ok = db.execute(
        text("SELECT core.touch_auth_session(:jti, :idle)"),
        {"jti": str(jti), "idle": AUTH_IDLE_TIMEOUT_MINUTES},
    ).scalar()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o cerrada. Inicie sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


async def assert_auth_session_async(db, payload: dict) -> None:
    jti = payload.get("jti") if isinstance(payload, dict) else None
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida; inicie sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await db.execute(
        text("SELECT core.touch_auth_session(:jti, :idle)"),
        {"jti": str(jti), "idle": AUTH_IDLE_TIMEOUT_MINUTES},
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o cerrada. Inicie sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
