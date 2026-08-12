# Albatros Biométrico (Chismoso)

Repo de **producto** — Control de Biométricos (asistencia / comedor vía **ISAPI Hikvision**).  
Workspace del colaborador: desarrolla aquí sin clonar todo el monorepo INTEGRADO.

| | |
|--|--|
| **GitHub** | [`perezrojas27/chismoso`](https://github.com/perezrojas27/chismoso) |
| **Embebido** | INTEGRADO → `modulos/biometrico/` |
| **Contrato** | [`CONTRATO_COLABORADOR.md`](CONTRATO_COLABORADOR.md) |

**Sync 2026-08-12:** árbol alineado con INTEGRADO (consola edge ampliada + modelo desacoplado edge/cloud).

---

## Modelo desacoplado (obligatorio)

```
LAN sede (relojes ISAPI)              Portal INTEGRADO (labs/prod)
┌─────────────────────────┐           ┌──────────────────────────────┐
│ Agente EDGE + consola   │  enroll / │ nginx · SPA /biometrico/     │
│ :8003  (Win / Pi / PC)  │  ingest / │ API /api/biometrico/*  JWT   │
│ C:\AlbatrosEdge o Docker│  heartbeat│ Postgres schema biometrico   │
└────────────▲────────────┘           └──────────────────────────────┘
             │ Digest ISAPI
┌────────────┴────────────┐
│ Reloj Hikvision :80     │
└─────────────────────────┘
```

| Capa | Dónde | Qué hace |
|------|--------|----------|
| **Edge** | Sede (`:8003`) | ISAPI, consola TI, SQLite outbox, sync → cloud |
| **Cloud** | Portal / este repo en lab | Reportes, ingest, vínculo GTH, JWT |
| **Consola** | Solo en el edge | Detectar / editar / probar / quitar relojes; clave ISAPI; acceso a la consola |
| **Hub** | Solo lectura de inventario | No escanea LAN ni guarda passwords ISAPI |

No publicar el edge en el compose del portal como solución definitiva (`biometrico-edge-lab` = UAT excepcional).

Detalle: [`docs/ARQUITECTURA_EDGE_CLOUD.md`](docs/ARQUITECTURA_EDGE_CLOUD.md) · [`docs/INSTALACION_AGENTE_SEDE.md`](docs/INSTALACION_AGENTE_SEDE.md).

---

## Stack

- Backend: Python · FastAPI · httpx (Digest) · SQLite (edge) / Postgres `biometrico` (portal)
- Frontend: Vite · React · TypeScript
- Roles INTEGRADO: `servicios_generales` · `gth` · `admin` (`client_id=biometrico`)

---

## Arranque rápido (lab local)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Lab sin IdP:
#   AUTH_DISABLED=true
#   ALLOW_LAB_MOCK=true
#   SOURCE=mock   # o hikvision si hay terminal en LAN

# Agente Edge + consola TI
uvicorn edge_app.main:app --reload --host 0.0.0.0 --port 8003

# Cloud / reportes
uvicorn cloud_app.main:app --reload --host 0.0.0.0 --port 8004

cd ../frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

| URL | Uso |
|-----|-----|
| http://localhost:5173 | SPA reportes |
| http://localhost:8003/ | Consola del agente (dispositivos) |
| http://localhost:8004 | API cloud |

### Agente en sede (Windows / Docker)

- Plantilla: `.env.edge-sede.example` + `docker-compose.edge-sede.yml`
- Windows lab: `C:\AlbatrosEdge` · WinSW `albatros-edge` · consola `:8003`
- Desde otra VLAN: túnel SSH `-L 18003:127.0.0.1:8003`

---

## Consola del agente (2026-08-12)

| Acción | Notas |
|--------|--------|
| Credenciales ISAPI | Usuario/clave del **reloj** (no de la consola) |
| Acceso a esta consola | Cambiar usuario/clave → `data/console_auth.json` |
| Detectar / agregar / **editar** / **probar** / quitar | IP, puerto, ubicación; sonda ISAPI |
| Formato hora 12h/24h en pantalla del reloj | **No** (web del terminal / ISAPI futuro) |

---

## Modos de datos

| Variable | Efecto |
|----------|--------|
| `SOURCE=hikvision` | Edge lee terminales ISAPI |
| `SOURCE=mock` | Lab sin reloj |
| `REPORT_DATA_MODE=store` | Reportes desde SQLite (recomendado) |
| `AUTH_DISABLED=true` | Lab sin JWT del portal |
| `ALLOW_LAB_MOCK=true` | Mock enroll/ingest en edge |

---

## Integración con INTEGRADO

1. Desarrollar y probar en este repo.  
2. Avisar al integrador (o PR) → importa a `modulos/biometrico/`.  
3. Integrador: compose/nginx labs · opcional **Importar manifiesto** en Admin · roles en Grupos.  
4. Manual integrador (monorepo): `docs/guias/MANUAL_INTEGRADOR_APLICACIONES.md`.

Manifiesto: [`integration/albatros.app.manifest.json`](integration/albatros.app.manifest.json).

**Grupos geográficos** del listado HikCentral **no** sustituyen `person_links` GTH — ver [`docs/VINCULO_GTH_BIOMETRICO.md`](docs/VINCULO_GTH_BIOMETRICO.md).

---

## Docs

| Documento | Contenido |
|-----------|-----------|
| [`CONTRATO_COLABORADOR.md`](CONTRATO_COLABORADOR.md) | Roles colaborador ↔ integrador |
| [`docs/ARQUITECTURA_EDGE_CLOUD.md`](docs/ARQUITECTURA_EDGE_CLOUD.md) | Edge vs cloud |
| [`docs/INSTALACION_AGENTE_SEDE.md`](docs/INSTALACION_AGENTE_SEDE.md) | Deploy agente sede |
| [`docs/ISAPI_ENDPOINTS.md`](docs/ISAPI_ENDPOINTS.md) | Endpoints usados |
| [`docs/ESTADO_ACTUAL_Y_PENDIENTES.md`](docs/ESTADO_ACTUAL_Y_PENDIENTES.md) | Estado vivo |
| [`docs/VINCULO_GTH_BIOMETRICO.md`](docs/VINCULO_GTH_BIOMETRICO.md) | Vínculo GTH |
| [`README_INTEGRADO.md`](README_INTEGRADO.md) | Empaquetado Docker/nginx portal |

---

*Producto Albatros Biométrico · integración con monorepo INTEGRADO*
