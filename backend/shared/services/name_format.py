"""Formato corto de nombres: PAULO A. PEREZ R."""

from __future__ import annotations

_PARTICLES = {
    "DE",
    "DEL",
    "LA",
    "LAS",
    "LOS",
    "Y",
    "DI",
    "DA",
    "SAN",
    "SANTA",
}


def _merge_particles(tokens: list[str]) -> list[str]:
    """Une partículas al token siguiente (p. ej. DE + LA + CRUZ → DE LA CRUZ)."""
    merged: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        parts = [tokens[i]]
        # Si el token actual es partícula, absorbe los siguientes
        # hasta incluir el primer token que no sea partícula.
        while i + 1 < n and tokens[i].upper() in _PARTICLES:
            i += 1
            parts.append(tokens[i])
        merged.append(" ".join(parts))
        i += 1
    return merged


def _initial(part: str) -> str:
    for ch in part.strip():
        if ch.isalnum():
            return ch.upper()
    return ""


def format_employee_name(full_name: str) -> str:
    """
    PAULO ANTONIO PEREZ ROJAS → PAULO A. PEREZ R.
    Con 3 partes: NOMBRE APELLIDO1 APELLIDO2 → NOMBRE APELLIDO1 A.
    Con 2 partes: NOMBRE APELLIDO (sin abreviatura).
    """
    raw = (full_name or "").strip()
    if not raw:
        return raw

    tokens = [t for t in raw.replace(",", " ").split() if t]
    parts = [p.upper() for p in _merge_particles(tokens)]
    if not parts:
        return raw

    if len(parts) >= 4:
        mid = _initial(parts[1])
        sur2 = _initial(parts[3])
        return f"{parts[0]} {mid}. {parts[2]} {sur2}."
    if len(parts) == 3:
        sur2 = _initial(parts[2])
        return f"{parts[0]} {parts[1]} {sur2}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0]
