"""
Autenticación JWT Albatros INTEGRADO.

Roles del módulo biométrico:
  - servicios_generales: ver/imprimir PDF de comedor
  - gth: comedor + asistencia + permisos de excepción
  - admin: todo + administración de dispositivos (TI)

En local: AUTH_DISABLED=true omite validación (desarrollo).
En portal: mismo JWT_SECRET_KEY que integrado-backend.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings

EXPECTED_ISS = "albatros_auth_integrado"
APP_CLIENT_ID = "biometrico"

# Roles canónicos + alias legacy del seed anterior
ROLE_SERVICIOS = "servicios_generales"
ROLE_GTH = "gth"
ROLE_ADMIN = "admin"

# Alias: consulta → SG, operador → gth
_ROLE_ALIASES: dict[str, frozenset[str]] = {
    ROLE_SERVICIOS: frozenset({ROLE_SERVICIOS, "consulta"}),
    ROLE_GTH: frozenset({ROLE_GTH, "operador"}),
    ROLE_ADMIN: frozenset({ROLE_ADMIN}),
}

ROLES_COMEDOR = (ROLE_SERVICIOS, ROLE_GTH, ROLE_ADMIN)
ROLES_ASISTENCIA = (ROLE_GTH, ROLE_ADMIN)
ROLES_GTH_OPS = (ROLE_GTH, ROLE_ADMIN)
ROLES_DEVICES = (ROLE_ADMIN,)

_bearer = HTTPBearer(auto_error=False)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET_KEY no configurado",
        )
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma rechazada o token inválido",
        ) from exc

    if payload.get("iss") and payload.get("iss") != EXPECTED_ISS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Emisor no reconocido",
        )
    if not payload.get("sub") or not payload.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
    return payload


def _expand_allowed(*allowed: str) -> set[str]:
    names: set[str] = set()
    for role in allowed:
        names |= _ROLE_ALIASES.get(role, frozenset({role}))
    return names


def _user_roles(payload: dict[str, Any]) -> set[str]:
    raw = (payload.get("app_roles") or {}).get(APP_CLIENT_ID) or []
    return {str(r) for r in raw}


def _has_any_app_role(payload: dict[str, Any], *allowed: str) -> bool:
    if payload.get("is_superadmin"):
        return True
    roles = _user_roles(payload)
    if not allowed:
        return bool(roles)
    return bool(roles & _expand_allowed(*allowed))


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if settings.auth_disabled:
        return {
            "payload": {
                "sub": "dev@goalbatros.com",
                "id": "00000000-0000-0000-0000-000000000001",
                "is_superadmin": True,
                "app_roles": {
                    APP_CLIENT_ID: [ROLE_ADMIN, ROLE_GTH, ROLE_SERVICIOS],
                },
            },
            "dev": True,
        }

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente",
        )
    payload = decode_access_token(credentials.credentials, settings)
    return {"payload": payload, "dev": False}


def require_app_access(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    payload = user["payload"]
    if not _has_any_app_role(payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sin rol para {APP_CLIENT_ID}",
        )
    return user


def require_roles(*allowed: str):
    async def _dep(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
        payload = user["payload"]
        if not _has_any_app_role(payload, *allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sin permiso para esta operación en Control de Biométricos",
            )
        return user

    return _dep


def user_can_manage_gth(user: dict[str, Any]) -> bool:
    """GTH / admin: ver y gestionar excepciones de comedor."""
    return _has_any_app_role(user["payload"], ROLE_GTH, ROLE_ADMIN)
