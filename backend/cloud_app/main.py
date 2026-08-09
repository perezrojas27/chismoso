from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings

from cloud_app.api.routes_exceptions import router as exceptions_router
from cloud_app.api.routes_health import router as health_router
from cloud_app.api.routes_person_linkage import router as person_linkage_router
from cloud_app.api.routes_reports import router as reports_router

settings = get_settings()

app = FastAPI(
    title="Albatros Biométrico",
    description=(
        "Cloud asistencia multi-sede: ingest Postgres + reportes JWT. "
        "Contrato /api/asistencia/v1"
    ),
    version="1.3.0",
)

# CORS restrictivo: orígenes desde CORS_ORIGINS (CSV). Si vacío, no se monta
# CORSMiddleware (mismo origen vía nginx) — nunca * + credentials.
_cors_origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(reports_router)
app.include_router(exceptions_router)
app.include_router(person_linkage_router)

_has_db = bool((settings.database_url or "").strip())
if _has_db:
    from cloud_app.api.routes_devices_cloud import router as devices_cloud_router

    app.include_router(devices_cloud_router)

# Ingest real (Postgres) por defecto. Mock lab solo con ALLOW_LAB_MOCK=true.
# Sin DATABASE_URL + lab mock: solo mock (desarrollo local sin PG).
if settings.allow_lab_mock and not _has_db:
    from cloud_app.api.routes_cloud_mock import router as cloud_mock_router

    app.include_router(cloud_mock_router)
else:
    from cloud_app.api.routes_ingest import router as ingest_router

    app.include_router(ingest_router)
    if settings.allow_lab_mock:
        # Añade lab/issue-enrollment; rutas solapadas quedan en ingest (primero).
        from cloud_app.api.routes_cloud_mock import router as cloud_mock_router

        app.include_router(cloud_mock_router)
