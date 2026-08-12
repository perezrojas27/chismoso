"""Auth de la consola local del agente edge (estilo software de sede)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from shared.config import Settings, get_settings

router = APIRouter(prefix="/api/edge-admin", tags=["edge-admin"])

# token -> (expires_at_epoch, username)
_sessions: dict[str, tuple[float, str]] = {}
_SESSION_TTL_SEC = 12 * 3600


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _admin_user(settings: Settings) -> str:
    try:
        from edge_app.services.console_auth_secrets import load_console_auth

        stored = load_console_auth(settings.edge_data_dir or None)
        if stored and stored.get("username"):
            return stored["username"]
    except Exception:
        pass
    return (settings.edge_admin_user or "admin").strip() or "admin"


def _admin_password(settings: Settings) -> str:
    try:
        from edge_app.services.console_auth_secrets import load_console_auth

        stored = load_console_auth(settings.edge_data_dir or None)
        if stored and stored.get("password"):
            return stored["password"]
    except Exception:
        pass
    return (settings.edge_admin_password or "").strip()


def _revoke_all_sessions() -> None:
    _sessions.clear()


def _password_ok(provided: str, expected: str) -> bool:
    if not expected:
        return False
    a = hashlib.sha256(provided.encode("utf-8")).digest()
    b = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


def _purge_expired() -> None:
    now = time.time()
    dead = [k for k, (exp, _) in _sessions.items() if exp <= now]
    for k in dead:
        _sessions.pop(k, None)


def issue_session(username: str) -> str:
    _purge_expired()
    token = secrets.token_urlsafe(32)
    _sessions[token] = (time.time() + _SESSION_TTL_SEC, username)
    return token


def revoke_session(token: str | None) -> None:
    if token:
        _sessions.pop(token.strip(), None)


def validate_session_token(token: str | None) -> str | None:
    if not token:
        return None
    _purge_expired()
    row = _sessions.get(token.strip())
    if not row:
        return None
    exp, username = row
    if exp <= time.time():
        _sessions.pop(token.strip(), None)
        return None
    return username


async def require_edge_console_auth(
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
    x_edge_admin_token: Annotated[str | None, Header(alias="X-Edge-Admin-Token")] = None,
) -> dict[str, Any]:
    """
    Protege la consola y las APIs de dispositivos del edge.

    - Si EDGE_ADMIN_PASSWORD está vacío: permite acceso (lab) pero marca open=True.
    - Si hay password: exige Bearer / X-Edge-Admin-Token de sesión tras login.
    """
    expected = _admin_password(settings)
    if not expected:
        return {
            "username": "lab-open",
            "open": True,
            "auth_required": False,
        }

    token = None
    if x_edge_admin_token:
        token = x_edge_admin_token.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    username = validate_session_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inicie sesión en la consola del agente (usuario/clave de sede).",
        )
    return {"username": username, "open": False, "auth_required": True}


@router.get("/status")
def console_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    from edge_app.services.console_auth_secrets import load_console_auth

    pwd = _admin_password(settings)
    isapi_pwd = (settings.effective_hikvision_password() or "").strip()
    stored = load_console_auth(settings.edge_data_dir or None)
    return {
        "console": "biometrico-edge",
        "site_code": settings.site_code,
        "site_name": settings.site_name,
        "auth_required": bool(pwd),
        "default_username": _admin_user(settings),
        "console_auth_from_file": bool(stored),
        "isapi_user": settings.effective_hikvision_user(),
        "isapi_password_configured": bool(isapi_pwd),
        "source": settings.source,
        "hikvision_use_https": settings.hikvision_use_https,
        "scan_seed": (settings.edge_scan_seed_host or settings.hikvision_host or "").strip(),
    }


@router.post("/login")
def login(body: LoginBody, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    expected = _admin_password(settings)
    if not expected:
        token = issue_session("lab-open")
        return {
            "token": token,
            "username": "lab-open",
            "auth_required": False,
            "message": "Consola abierta (sin EDGE_ADMIN_PASSWORD).",
        }

    user_ok = hmac.compare_digest(
        body.username.strip().encode("utf-8"),
        _admin_user(settings).encode("utf-8"),
    )
    if not user_ok or not _password_ok(body.password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    token = issue_session(body.username.strip())
    return {
        "token": token,
        "username": body.username.strip(),
        "auth_required": True,
        "expires_in_seconds": _SESSION_TTL_SEC,
        "message": "Sesión de consola iniciada",
    }


@router.post("/logout")
def logout(
    authorization: Annotated[str | None, Header()] = None,
    x_edge_admin_token: Annotated[str | None, Header(alias="X-Edge-Admin-Token")] = None,
) -> dict[str, str]:
    token = None
    if x_edge_admin_token:
        token = x_edge_admin_token.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    revoke_session(token)
    return {"message": "Sesión cerrada"}


class IsapiCredentialsBody(BaseModel):
    username: str = Field(default="admin", min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/isapi-credentials")
def save_isapi_credentials(
    body: IsapiCredentialsBody,
    _: dict = Depends(require_edge_console_auth),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from edge_app.services.isapi_secrets import save_isapi_credentials

    save_isapi_credentials(body.username.strip(), body.password)
    return {
        "message": "Credenciales ISAPI guardadas en el agente (solo este servidor).",
        "isapi_user": body.username.strip(),
        "isapi_password_configured": True,
        "site_code": settings.site_code,
    }


class ChangeConsolePasswordBody(BaseModel):
    current_password: str = Field(default="", max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    new_username: str | None = Field(default=None, max_length=64)


@router.post("/change-password")
def change_console_password(
    body: ChangeConsolePasswordBody,
    session: dict = Depends(require_edge_console_auth),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Cambia usuario/clave de la consola local (persistido en data/console_auth.json
    y sincronizado a EDGE_ADMIN_* del .env).
    Si aún no hay clave (lab abierto), current_password puede ir vacío.
    """
    from pathlib import Path

    from edge_app.services.console_auth_secrets import (
        save_console_auth,
        sync_env_console_credentials,
    )

    expected = _admin_password(settings)
    if expected:
        if not _password_ok(body.current_password or "", expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "La contraseña actual de la consola no es correcta. "
                    "Use la clave con la que inició sesión (o EDGE_ADMIN_PASSWORD del .env)."
                ),
            )
    elif (body.current_password or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La consola aún no tiene clave; deje «contraseña actual» vacía.",
        )

    new_pwd = body.new_password.strip()
    if len(new_pwd) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 8 caracteres.",
        )

    new_user = (body.new_username or "").strip() or _admin_user(settings)
    data_dir = (settings.edge_data_dir or "").strip() or None
    try:
        saved_path = save_console_auth(new_user, new_pwd, data_dir)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo guardar la clave de consola: {exc}",
        ) from exc

    env_path = Path(__file__).resolve().parents[2] / ".env"
    env_synced = sync_env_console_credentials(
        new_user, new_pwd, env_path=env_path
    )

    # Invalidar caché de Settings para que el próximo login lea la clave nueva del .env
    try:
        get_settings.cache_clear()
    except Exception:
        pass

    _revoke_all_sessions()
    token = issue_session(new_user)
    return {
        "message": (
            "Contraseña de la consola actualizada. Sesión renovada."
            + (" (.env sincronizado)" if env_synced else "")
        ),
        "username": new_user,
        "auth_required": True,
        "token": token,
        "expires_in_seconds": _SESSION_TTL_SEC,
        "previous_open_mode": bool(session.get("open")),
        "saved": True,
        "auth_file": saved_path.name,
        "env_synced": env_synced,
    }
