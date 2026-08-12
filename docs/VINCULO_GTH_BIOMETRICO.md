# Vínculo empleado GTH ↔ ID biométrico

**Fecha:** 2026-08-08 (deploy oficina ✅ · commit `7fd8b6b`)  
**Actualizado:** 2026-08-10 — aclaración grupos geográficos vs datos visibles en INTEGRADO  
**Módulo:** `client_id=biometrico`  
**Análogo:** vinculación correo ↔ GTH (`/api/hr/employee-linkage`, `gth-vinculo-correo.html`)  
**Labs:** oficina `:8090` y casero `:8080` (cloud bio en casero desde `4f36eaa`).  
**Prod:** no — ver [`SEMANA_UAT_LABS_SIN_PROD_20260808.md`](https://github.com/jpvalor-pololo/INTEGRADO/blob/main/docs/guias/SEMANA_UAT_LABS_SIN_PROD_20260808.md).

## Problema

Los relojes Hikvision identifican personas con **`employeeNo`** (ID propio del firmware), no con la cédula GTH.  
Para saber **quién de una sede marcó y quién no**, hay que cruzar:

- Empleados activos de GTH en esa sede (`hr.employees.site_id` → `core.sites`)
- Marcajes del día (`biometrico.events.person_external_id`)
- **Mapa** `person_external_id` ↔ `hr.employees.id`

Sin el mapa, solo se ven IDs del reloj / nombres del dispositivo.

## Qué datos del biométrico ve INTEGRADO hoy (2026-08-10)

| Dato | ¿Visible en cloud INTEGRADO? | Notas |
|------|------------------------------|--------|
| `employeeNo` (`person_external_id`) | Sí | En eventos e ingest |
| Nombre en el terminal | Sí (si el firmware lo entrega) | UserInfo/Search ISAPI |
| Sede del **agente edge** | Sí | Un proceso edge = una sede geográfica (`site_id` / `site_code`) |
| Campo `department` en eventos | Parcial | El DS-K1T8003MF **no** expone depto fiable en UserInfo; hay mapa local de respaldo (export HikCentral) |
| **Grupos geográficos** del listado de Personas (HikCentral / software biométrico) | **No** | No hay sync de grupos de usuarios hacia `biometrico.*` |

### Grupos por ubicación vs vínculo GTH

En operación, al cargar personas en el biométrico a menudo se las asigna a **grupos ligados a ubicación**. Ese catálogo vive en HikCentral / firmware, **no** en el schema `biometrico` de INTEGRADO.

- La geografía que sí discrimina el diseño actual es la **sede del edge** que envía el marcaje, no el grupo interno del listado de personas.
- Esos grupos **no sustituyen** `person_links`: sirven (en el mejor caso, si se sincronizaran) para rotular o filtrar, no para saber qué ficha GTH es cada `employeeNo`.
- Camino canónico para presencia GTH: `biometrico.person_links` (+ `site_map` sede edge ↔ `core.sites`).
- Mejora futura: auto-sugerencia si `employeeNo` ≈ cédula normalizada; o sync explícito de grupos si ISAPI/export lo permite (pendiente de exploración).

## Modelo de datos (schema `biometrico`)

| Tabla | Rol |
|-------|-----|
| `person_links` | `person_external_id` UNIQUE ↔ `employee_id` (UUID lógico GTH) + `cedula` |
| `site_map` | `biometric_site_id` ↔ `core_site_id` (alineación de sedes) |

Sin FK ORM a `hr`/`core` (mismo criterio que el resto del módulo).

DDL: [`db_init/biometrico_tables.sql`](../../db_init/biometrico_tables.sql).

## API (roles `gth` / `admin`)

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/api/biometrico/person-linkage/active` | Empleados GTH + estado vínculo |
| GET | `/api/biometrico/person-linkage/persons/unlinked` | IDs vistos en eventos sin vínculo |
| POST | `/api/biometrico/person-linkage/{employee_id}/link` | Body `{ person_external_id }` |
| POST | `/api/biometrico/person-linkage/{employee_id}/unlink` | Quitar vínculo |
| GET | `/api/biometrico/person-linkage/presence?date=&core_site_id=` | Presentes / ausentes / sin vínculo |

## UI

SPA `/biometrico/` → pestaña **Vínculo GTH** (visible con rol GTH/admin).

## Flujo operativo

1. Asegurar marcajes en lab (edge + ingest).  
2. Admin GTH: vincular employeeNo ↔ ficha.  
3. (Recomendado) Insertar fila en `biometrico.site_map` para la sede.  
4. Consultar presencia del día.

## Relación con datos de INTEGRADO

- **Lee** `hr.employees` y `core.sites` (solo lectura).  
- **Escribe** solo en `biometrico.person_links` / `site_map`.  
- No modifica GTH ni el firmware del reloj.

## Pendiente (siguiente)

- UI select de sedes GTH (hoy UUID manual en presencia).  
- Auto-sugerencia si `employeeNo` == cédula normalizada.  
- Enriquecer PDF asistencia con cédula GTH.  
- Explorar sync de **grupos geográficos** biométricos (si API/export lo permite) — no reemplaza `person_links`.  
- UAT roles biométrico en Admin → Grupos (labs).
