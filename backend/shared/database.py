"""Engine sync SQLAlchemy desde DATABASE_URL (PostgreSQL)."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url
    try:
        from shared.config import get_settings

        return (get_settings().database_url or "").strip()
    except Exception:
        return ""


def get_engine() -> Engine:
    """Crea el engine lazy. Falla si no hay DATABASE_URL."""
    global _engine, _SessionLocal
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL no configurado")
    if _engine is None:
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def SessionLocal() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI. Solo usar en rutas cloud que necesiten Postgres."""
    if not get_database_url():
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL no configurado",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_available() -> bool:
    return bool(get_database_url())
