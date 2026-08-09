# Albatros Biométrico (Chismoso)

Repo de **producto** — asistencia / comedor (ISAPI Hikvision).  
Este es el workspace del colaborador: desarrolla aquí sin clonar el monorepo INTEGRADO.

> **Export 2026-08-08:** árbol alineado con el código vivo en INTEGRADO (`modulos/biometrico/`), tras la integración y cambios posteriores (consola edge, vínculo GTH, packaging portal).

Contrato colaborador ↔ integrador: [`CONTRATO_COLABORADOR.md`](CONTRATO_COLABORADOR.md).

## Stack

- Backend: Python · FastAPI · httpx (Digest) · SQLite (lab) / Postgres schema `biometrico` (portal)
- Frontend: Vite · React · TypeScript
- Roles INTEGRADO: `servicios_generales` · `gth` · `admin` (`client_id=biometrico`)

## Arranque rápido (lab local)

```bash
cd backend
# Windows: ..\.venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# En .env para lab sin IdP:
#   AUTH_DISABLED=true
#   ALLOW_LAB_MOCK=true
#   SOURCE=mock   # o hikvision si tienes terminal en LAN

# Agente Edge + consola TI (puerto 8003)
uvicorn edge_app.main:app --reload --host 0.0.0.0 --port 8003

# Cloud / reportes (puerto 8004)
uvicorn cloud_app.main:app --reload --host 0.0.0.0 --port 8004

cd ../frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

| URL | Uso |
|-----|-----|
| http://localhost:5173 | SPA (proxy `/api` → backend) |
| http://localhost:8003/ | Consola del agente (dispositivos ISAPI) |
| http://localhost:8004 | API cloud / reportes |

## Modos de datos

| Variable | Efecto |
|----------|--------|
| `SOURCE=mock` / `hikvision` | Mock local o terminales ISAPI |
| `REPORT_DATA_MODE=store` | Reportes leen SQLite (recomendado en lab) |
| `DATABASE_URL=` (vacío) | Lab sin Postgres |
| `AUTH_DISABLED=true` | Lab sin JWT del portal |
| `ALLOW_LAB_MOCK=true` | Mock enroll/ingest en el edge |

**Modo portal (no necesario para desarrollar features):** JWT del IdP INTEGRADO, `DATABASE_URL` al schema `biometrico`, SPA bajo `/biometrico/`. Detalle de embebido: `README_INTEGRADO.md` (referencia; el deploy lo hace el integrador).

## Entrega de cambios

1. Trabaja en este repo (rama / PR en `perezrojas27/chismoso`).
2. El integrador **importa** a `modulos/biometrico/` del monorepo y despliega labs.
3. No hace falta tocar nginx, compose ni `seed_roles` del portal.

## Docs

- [`CONTRATO_COLABORADOR.md`](CONTRATO_COLABORADOR.md)
- `docs/ARQUITECTURA_EDGE_CLOUD.md`
- `docs/ISAPI_ENDPOINTS.md`
- `docs/INSTALACION_AGENTE_SEDE.md`
- `docs/GUIA_COLABORADOR_ASISTENCIA_ISAPI_MULTI_SEDE.md`
- `integration/albatros.app.manifest.json`
