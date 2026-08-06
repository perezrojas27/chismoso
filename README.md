# Albatros Biométrico (Chismoso)

> **2026-08-06 — Integrado en el monorepo Albatros INTEGRADO.**  
> Desarrollo y deploys: [`jpvalor-pololo/INTEGRADO`](https://github.com/jpvalor-pololo/INTEGRADO) → `modulos/biometrico/`.  
> Handoff: [`HANDOFF_INTEGRADO_20260806.md`](HANDOFF_INTEGRADO_20260806.md).


Módulo de **asistencia / comedor** para Albatros INTEGRADO. Fuente de marcajes: **ISAPI Hikvision** (no OpenAPI HikCentral).

Arquitectura multi-sede: **un agente edge por oficina** + reportes cloud sobre eventos normalizados.  
Ver `docs/ARQUITECTURA_EDGE_CLOUD.md`.

## Stack

- Backend: Python · FastAPI · httpx (Digest) · SQLite (store local)
- Frontend: Vite · React · TypeScript
- Roles INTEGRADO: `servicios_generales` · `gth` · `admin` (`client_id=biometrico`)

## Arranque rápido

```bash
cd backend
# Activar entorno (Windows): ..\.\.venv\Scripts\activate
# Activar entorno (Linux): source .venv/bin/activate
pip install -r requirements.txt
# Configuración inicial: copy .env.example .env (Windows) / cp .env.example .env (Linux)

# Arrancar Agente Edge (Puerto 8003)
uvicorn edge_app.main:app --reload --host 0.0.0.0 --port 8003

# Arrancar Cloud App / Reportes (Puerto 8004)
uvicorn cloud_app.main:app --reload --host 0.0.0.0 --port 8004

cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

UI: http://localhost:5173 — proxy `/api` → backend.

## Modos de datos

| Variable | Efecto |
|----------|--------|
| `SOURCE=hikvision` | Edge lee terminales ISAPI |
| `REPORT_DATA_MODE=store` | Reportes leen SQLite (recomendado) |
| `AUTO_SYNC_ON_REPORT=true` | Sync ISAPI→store al generar (lab local) |
| `REPORT_DATA_MODE=live` | ISAPI en cada request (legado) |

## Reportes

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/biometrico/reports/attendance?from_date=&to_date=&site_id=` | Primera/última marca |
| `GET /api/biometrico/reports/cafeteria?date=&site_id=` | Comedor ≤ corte (+ excepciones GTH) |
| `GET .../pdf` | PDF membretado |

## Edge / mock cloud

| Endpoint | Uso |
|----------|-----|
| `POST /api/biometrico/edge/sync` | Pull ISAPI → store |
| `GET /api/biometrico/edge/sites` | Sedes |
| `POST /api/asistencia/v1/agents/enroll` | Mock enroll INTEGRADO |
| `POST /api/asistencia/v1/sites/{id}/ingest` | Mock ingest |

## Docs

- `docs/ARQUITECTURA_EDGE_CLOUD.md`
- `docs/ISAPI_ENDPOINTS.md`
- `docs/INSTALACION_AGENTE_SEDE.md`
- `integration/albatros.app.manifest.json`
