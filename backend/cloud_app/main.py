from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cloud_app.api.routes_cloud_mock import router as cloud_mock_router
from cloud_app.api.routes_exceptions import router as exceptions_router
from cloud_app.api.routes_health import router as health_router
from cloud_app.api.routes_reports import router as reports_router

app = FastAPI(
    title="Albatros Biométrico",
    description=(
        "Módulo asistencia multi-sede ready: edge ISAPI + store local + reportes. "
        "Contrato mock INTEGRADO en /api/asistencia/v1"
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(reports_router)
app.include_router(exceptions_router)
app.include_router(cloud_mock_router)
