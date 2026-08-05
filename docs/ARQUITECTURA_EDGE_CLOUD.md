# Arquitectura edge / cloud — Asistencia biométrica (Albatros INTEGRADO)

Alineado a la guía multi-sede ISAPI (julio 2026). **OpenAPI HikCentral queda fuera del producto.**

## Piezas

| Pieza | Rol |
|-------|-----|
| **Edge** (`backend/app/edge/`) | ISAPI en LAN de **una sede**, store SQLite, cola outbox, cliente enroll/ingest/heartbeat |
| **Cloud-app** (reportes + UI) | JWT roles, reportes desde store, admin de sedes/dispositivos **reportados** |
| **Mock INTEGRADO** (`/api/asistencia/v1`) | Contrato listo para labs sin cloud real |

Un proceso edge = **una sede geográfica**. Cloud no guarda passwords ISAPI.

## Flujo de datos

```text
Terminal Hikvision (ISAPI)
        │
        ▼
  sync edge → events.sqlite3 (+ outbox)
        │
        ├──► reportes UI/PDF (leen store)
        └──► POST ingest → INTEGRADO (o mock)
```

## Config clave (`.env`)

```env
SITE_CODE=oficina_central
REPORT_DATA_MODE=store
AUTO_SYNC_ON_REPORT=true
SOURCE=hikvision
INTEGRADO_BASE_URL=          # vacío = mock local
ENROLLMENT_TOKEN=lab-token
AGENT_CREDENTIAL=
```

## Endpoints edge / mock

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/api/biometrico/edge/sites` | Listado sedes + sede actual |
| POST | `/api/biometrico/edge/sync` | Pull ISAPI → store |
| POST | `/api/biometrico/edge/push` | Outbox → cloud |
| POST | `/api/biometrico/edge/heartbeat` | Salud agente |
| POST | `/api/asistencia/v1/agents/enroll` | Mock enroll |
| POST | `/api/asistencia/v1/sites/{id}/ingest` | Mock ingest |
| POST | `/api/asistencia/v1/sites/{id}/heartbeat` | Mock heartbeat |

Reportes aceptan `site_id` opcional.

## Regla de oro

- Socket a `192.168.x.x/.../ISAPI/...` → **edge**
- PDF/Excel de asistencia → **cloud-app** sobre datos ya ingeridos

## Personas / ausencias

GTH es maestro de personas en INTEGRADO. Este módulo **no** duplica el padrón completo. Las ausencias totales requieren cruzar eventos con el directorio GTH (`employee_code` / cédula), no solo el buffer del terminal.

## Checklist guía (§14) — estado local

- [x] OpenAPI HikCentral fuera del camino feliz (solo ISAPI)
- [x] `site_id` en sedes / eventos / filtro UI
- [x] Módulo edge separable + store SQLite + outbox
- [x] Reportes leen store (`REPORT_DATA_MODE=store`)
- [x] `external_event_id` idempotente
- [x] Cliente + mock enroll / ingest / heartbeat
- [x] Roles UI admin / gth / servicios_generales
- [x] Filtro por sede
- [x] `.env.example` del agente
- [ ] Empaquetado instalable por sede (Docker/servicio Windows) — pendiente
- [ ] README instalación TI 1–2 pág. por sede — ver `docs/INSTALACION_AGENTE_SEDE.md`
- [ ] Cola 1 h cloud caído + sync sin duplicar — probar en lab
- [ ] Mapeo persona → código empleado GTH — documentado, pendiente integración directorio

## Hermes (futuro cloud)

Kinds sugeridos: sync fallida, dispositivo offline (además de comedor/permiso GTH ya en manifiesto).
