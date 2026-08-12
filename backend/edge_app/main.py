import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from edge_app.api.routes_devices import router as devices_router
from edge_app.api.routes_edge import router as edge_router
from edge_app.api.routes_edge_admin import router as edge_admin_router
from edge_app.api.routes_health import router as health_router
from edge_app.runtime_loop import runtime_loop

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

CONSOLE_DIR = Path(__file__).resolve().parent / "console"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import os

    from shared.config import get_settings

    settings = get_settings()
    if (settings.edge_data_dir or "").strip():
        os.environ["EDGE_DATA_DIR"] = settings.edge_data_dir.strip()
        Path(settings.edge_data_dir.strip()).mkdir(parents=True, exist_ok=True)

    stop = asyncio.Event()
    task = asyncio.create_task(runtime_loop(stop), name="biometrico-edge-loop")
    logger.info("Edge runtime loop started")
    logger.info("Consola de sede: http://0.0.0.0:8003/  (UI local de dispositivos)")
    try:
        yield
    finally:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=15)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
        logger.info("Edge runtime loop stopped")


app = FastAPI(
    title="Albatros Biométrico — Edge",
    description=(
        "Agente de sede: consola local (detectar/configurar relojes) + ISAPI + "
        "outbox + enroll/heartbeat/ingest hacia INTEGRADO."
    ),
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(edge_admin_router)
app.include_router(devices_router)
app.include_router(edge_router)

if CONSOLE_DIR.is_dir():
    app.mount("/console", StaticFiles(directory=str(CONSOLE_DIR)), name="console-assets")

    @app.get("/")
    async def console_home():
        return FileResponse(CONSOLE_DIR / "index.html")
