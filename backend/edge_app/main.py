from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edge_app.api.routes_devices import router as devices_router
from edge_app.api.routes_edge import router as edge_router
from edge_app.api.routes_health import router as health_router

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
app.include_router(devices_router)
app.include_router(edge_router)
