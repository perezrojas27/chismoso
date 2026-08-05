# Guía para colaborador — Asistencia biométrica ISAPI (multi-sede → INTEGRADO)

**Versión:** 1.0  
**Fecha:** 2026-07-31  
**Audiencia:** desarrollador de la app de asistencia (código ya funcional en LAN local)  
**Propósito:** asimilar la arquitectura edge/cloud multi-sede **antes** de entregar el código para integrar al portal Albatros INTEGRADO  
**Estado INTEGRADO:** listo en contexto/normativa para recibir el módulo cuando se entregue un paquete alineado a esta guía

---

## 1. Resumen ejecutivo

La aplicación de reportes de asistencia **ya funciona en local** contra biometrías Hikvision vía **ISAPI**. El destino final es el portal **INTEGRADO** en la nube (`integrado.goalbatros.com`), con roles `admin`, `gth` y `servicios_generales`.

**OpenAPI de HikCentral queda excluida de forma definitiva** (restricciones de versión de software y licencia). No invertir más esfuerzo en Artemis/AppKey.

Los biometrías viven en **LANs de oficinas** geográficamente distintas (ej. Maiquetía, Maracay, Punto Fijo, Tacariguas). INTEGRADO en cloud **no** puede hablar ISAPI directo a esas redes. Por tanto el producto se divide en:

| Pieza | Dónde corre | Responsabilidad |
|-------|-------------|-----------------|
| **Agente edge** | Un instalable **por sede** (PC/VM en la LAN de esa oficina) | ISAPI, descubrimiento/alta de dispositivos, sync de eventos hacia cloud |
| **Módulo INTEGRADO** | Hosting cloud (mismo ecosistema del portal) | SSO JWT, roles, UI Hub, BD, reportes, altas de sede, salud de agentes |

**Tu trabajo ahora:** reestructurar el código local funcional para que encaje en el rol de **agente edge multi-sede-ready** + separar limpio lo que será **API/UI de reportes en cloud**. Así la integración a INTEGRADO será un empaquetado, no un rediseño de emergencia.

---

## 2. Decisiones de producto (no negociables)

1. **Fuente de marcajes = ISAPI** a cada terminal (p. ej. DS-K1T8003MF), no HikCentral OpenAPI.
2. **Un agente por sede geográfica.** No un solo proceso en una oficina intentando alcanzar IPs de otra ciudad.
3. **Cloud no guarda ni usa** las contraseñas ISAPI de los terminales en el camino feliz (viven en el edge). Cloud recibe **eventos ya normalizados**.
4. **Descubrimiento y alta interactiva de dispositivos** ocurre en la LAN (vía el agente), no desde el navegador del usuario en Internet hacia IPs privadas.
5. **Alta interactiva de sedes** cuando TI de esa oficina tenga red/dispositivos listos: portal crea sede → token → se instala/configura el agente allí.
6. **GTH es maestro de personas** en el ecosistema Albatros. No duplicar el padrón completo en silo; cruzar por código empleado / cédula / `employeeNo` alineado.
7. **Notificaciones futuras** (sync fallida, dispositivo offline) vía **Hermes** en INTEGRADO, no SMTP ad hoc en el edge hacia Internet corporativo.
8. Software Hikvision en el servidor local (iVMS / herramientas SADP, etc.) puede seguir existiendo para **configuración TI**, pero **no** es la API de reportes del producto.

---

## 3. Arquitectura objetivo

```text
                    INTEGRADO (nube)
                 ┌─────────────────────┐
  Usuarios ────► │ UI portal + JWT     │
                 │ API reportes/roles  │
                 │ schema attendance   │
                 │ ingest + heartbeat  │
                 └─────────▲───────────┘
                           │ HTTPS saliente (ingest)
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────┴─────┐     ┌─────┴─────┐     ┌─────┴─────┐
   │ Edge      │     │ Edge      │     │ Edge      │
   │ Maiquetía │     │ Maracay   │     │ …         │
   │ ISAPI LAN │     │ ISAPI LAN │     │           │
   └─────▲─────┘     └─────▲─────┘     └───────────┘
         │                 │
    Terminales          Terminales
```

### Camino de red

| Camino | Uso |
|--------|-----|
| **HTTPS outbound** edge → INTEGRADO | Principal: ingest de eventos + heartbeat |
| **Tailscale / mesh / VPN** (opcional por sede) | Solo ops: SSH, soporte, forzar sync si hace falta |
| ISAPI expuesto a Internet | **Prohibido** |

No se requiere VPN entre sedes (Maiquetía ↔ Maracay). Todas hablan con cloud; cloud es el hub de datos.

---

## 4. Modelo de datos lógico (preparar en tu app)

Usa nombres equivalentes aunque aún no exista PostgreSQL cloud; facilita el mapeo.

### 4.1 `sites` (sedes)

| Campo | Notas |
|-------|--------|
| `id` (UUID) | Estable |
| `code` | Corto único: `maiquetia`, `maracay`, `punto_fijo`, `tacariguas` |
| `name` | Nombre humano |
| `timezone` | Ej. `America/Caracas` |
| `status` | `pending` \| `active` \| `disabled` |
| `created_at` / `updated_at` | |

### 4.2 `devices` (dispositivos biométricos)

| Campo | Notas |
|-------|--------|
| `id` (UUID) | |
| `site_id` | Obligatorio — nunca un dispositivo “huérfano” |
| `name` / `alias` | Ej. “Entrada principal” |
| `model` | Ej. DS-K1T8003MF |
| `serial` / `mac` | Si ISAPI lo expone |
| `host` | IP o hostname **local** (solo tiene sentido en el edge) |
| `port` | Típicamente 80/443 |
| `isapi_user` | **Solo en edge** (secreto) |
| `isapi_password` | **Solo en edge** (secreto) |
| `status` | `candidate` \| `active` \| `disabled` \| `offline` |
| `last_seen_at` | Reportado por heartbeat |

### 4.3 `events` (marcajes normalizados)

| Campo | Notas |
|-------|--------|
| `id` (UUID) | Id interno |
| `site_id` | |
| `device_id` | |
| `external_event_id` | Id estable del evento en el dispositivo/API — **clave de idempotencia** |
| `occurred_at` | Timestamp con TZ |
| `person_external_id` | Id en el terminal / employeeNo |
| `person_name` | Opcional, display |
| `employee_code` | Para cruzar con GTH (cedula/código) cuando exista |
| `event_type` | `in` / `out` / `unknown` / código ACS |
| `success` | bool |
| `raw_payload` | Opcional (JSON) para depuración — no enviar siempre a cloud si es pesado |

**Idempotencia cloud:** único por `(site_id, device_id, external_event_id)` o hash equivalente.

### 4.4 Agente / enrollment

| Concepto | Notas |
|----------|--------|
| `enrollment_token` | Generado en cloud al crear sede; caduca; un uso o rotatorio |
| `agent_credential` | Tras enroll: token de largo plazo por sede |
| `agent_version` | Semver del instalable |
| `last_heartbeat_at` | |
| `last_sync_cursor` | Por dispositivo o global — para no reenviar eventos |

---

## 5. Separación de capas en tu código actual

Hoy probablemente tienes un monolito local (UI + ISAPI + reportes). Prepáralo así:

### 5.1 Paquete A — `edge` (se queda en cada oficina)

Responsabilidades:

- Cliente ISAPI (auth Digest/Basic, timeouts, reintentos).
- Descubrimiento / probe de dispositivos en LAN (el módulo interactivo que ya avanzaste).
- Inventario local de dispositivos de **esta** sede.
- Poll o pull de eventos ACS/asistencia desde cada dispositivo activo.
- Cursor/cola local (SQLite o archivos) por si cloud está caído: **no perder marcajes**.
- Cliente HTTP hacia INTEGRADO: enroll, ingest, heartbeat.
- Config: `SITE_CODE` o token de enrollment, `INTEGRADO_BASE_URL`, secretos ISAPI.

**No** debe depender de JWT de usuarios del portal para hablar con los terminales.

### 5.2 Paquete B — `cloud-app` (irá a INTEGRADO)

Responsabilidades (hoy pueden seguir en local como “modo demo”, pero desacopladas):

- Autenticación de usuarios (luego = JWT INTEGRADO).
- Autorización por roles.
- Reportes: comedor / presencia / asistencia RH / exports.
- Admin: sedes, tokens, listado de dispositivos **reportados**, salud.
- Lectura solo desde BD/cache de eventos (no llamar ISAPI).

### 5.3 Regla de oro de refactor

> Cualquier función que abra un socket a `http://192.168.x.x/.../ISAPI/...` pertenece al **edge**.  
> Cualquier función que arme un PDF/Excel de asistencia del mes pertenece al **cloud-app** (sobre datos ya ingeridos).

Si hoy el botón “Generar reporte” llama ISAPI en vivo, cámbialo a:

1. (Opcional) pedir al edge “sync ahora”, o  
2. Generar el reporte desde la tabla/cache local de eventos,  
y deja listo el mismo query para cuando la tabla viva en PostgreSQL cloud.

---

## 6. Flujo de alta de sede (interactivo)

Objetivo: agregar Maiquetía, Maracay, etc. cuando cada LAN esté lista, sin redeploy global.

```text
1. Admin (portal) crea sede → status=pending → recibe enrollment_token
2. TI en la oficina instala el agente edge
3. Configura INTEGRADO_BASE_URL + enrollment_token
4. Agente POST /agents/enroll → recibe agent_credential + site_id
5. Sede pasa a active
6. Operador usa UI de descubrimiento (local al agente o proxy admin→agente)
7. Confirma dispositivos → active en inventario
8. Agente comienza sync periódico de eventos
```

**Checklist TI por sede (para tu documentación de instalación):**

- [ ] Terminales en red, IPs conocidas o descubribles  
- [ ] Usuario/clave ISAPI por dispositivo (o plantilla)  
- [ ] NTP / hora correcta en terminales y en el PC del agente  
- [ ] Salida HTTPS desde el PC del agente hacia INTEGRADO (firewall)  
- [ ] (Opcional) nodo Tailscale en ese PC para soporte  
- [ ] Software Hikvision de configuración instalado solo si lo necesita el descubrimiento/alta de personas  

---

## 7. Contrato edge → cloud (diseño para el colaborador)

Implementa **stubs o un “modo cloud mock”** ya, aunque INTEGRADO aún no exponga los endpoints. Cuando integremos, solo cambiaremos la URL base.

Auth agente: header tipo `Authorization: Bearer <agent_credential>` o `X-Agent-Token` (acordaremos el nombre exacto en la integración). **No** uses el JWT de un usuario humano.

### 7.1 Enroll

`POST /api/asistencia/v1/agents/enroll`

```json
{
  "enrollment_token": "...",
  "agent_version": "1.2.0",
  "hostname": "pc-maiquetia-01"
}
```

Respuesta (ejemplo):

```json
{
  "site_id": "uuid",
  "site_code": "maiquetia",
  "agent_credential": "...",
  "ingest_url": "/api/asistencia/v1/sites/{site_id}/ingest"
}
```

### 7.2 Ingest de eventos

`POST /api/asistencia/v1/sites/{site_id}/ingest`

```json
{
  "agent_version": "1.2.0",
  "events": [
    {
      "device_id": "uuid-o-serial-local-mapeado",
      "external_event_id": "devSerial:20260731T080112:12345",
      "occurred_at": "2026-07-31T08:01:12-04:00",
      "person_external_id": "10023",
      "person_name": "Ana Pérez",
      "employee_code": "V12345678",
      "event_type": "in",
      "success": true
    }
  ]
}
```

Respuesta: lista de aceptados / duplicados / rechazados. El edge debe marcar cursor solo en aceptados+duplicados (idempotentes).

### 7.3 Heartbeat + inventario de dispositivos

`POST /api/asistencia/v1/sites/{site_id}/heartbeat`

```json
{
  "agent_version": "1.2.0",
  "devices": [
    {
      "device_id": "uuid",
      "status": "online",
      "last_event_at": "2026-07-31T08:01:12-04:00",
      "host": "192.168.10.51"
    }
  ],
  "sync": {
    "ok": true,
    "last_success_at": "2026-07-31T08:05:00-04:00",
    "pending_events": 0
  }
}
```

### 7.4 Registro / sync de inventario de dispositivos (opcional pero útil)

`POST /api/asistencia/v1/sites/{site_id}/devices/upsert`

Para que el admin en cloud vea los dispositivos que el edge acaba de descubrir/confirmar, sin conocer las claves ISAPI.

---

## 8. Roles y reportes (cloud)

`client_id` tentativo: `asistencia_biometrico` (ajustable al integrar).

| Rol | privilege_rank | Qué ve / hace |
|-----|----------------|---------------|
| `servicios_generales` | 40 | Reportes operativos (ej. lista comedor / presencia del día) en **sedes asignadas** |
| `gth` | 50 | Asistencia por persona/rango, faltas/tardanzas, export; una sede o consolidado |
| `admin` | 90 | Sedes, enrollment, dispositivos (inventario), salud agentes, forzar sync |

Preparar en tu UI actual:

- Menús/pantallas etiquetadas por rol (aunque en local uses un selector “simular rol”).
- Filtro **obligatorio** `site_id` (o “todas” solo para gth/admin).
- No mostrar configuración ISAPI a roles que no sean admin de edge (y en cloud, admin no ve passwords).

Reglas de negocio RH (tolerancia tardanza, turnos nocturnos, franja comedor) deben vivir en **configuración de la app**, no hardcodeadas a una sola oficina: preferir tablas/config por `site_id` (franja comedor distinta en Maracay vs Maiquetía).

---

## 9. Estrategias recomendadas (orden de trabajo del colaborador)

### Fase 0 — Congelar decisiones locales

- Documentar endpoints ISAPI reales que ya usas (paths, auth, paginación de eventos).
- Documentar si el descubrimiento usa SADP/SDK Hikvision o solo probe HTTP por rango/IP manual.
- Listar secretos y dónde viven hoy.

### Fase 1 — Introducir `site_id` en todo

- Aunque hoy haya una sola oficina, crea sede `default` o `oficina_central`.
- Todo dispositivo y todo evento lleva `site_id`.
- Esto evita rewrites dolorosos al abrir la segunda sede.

### Fase 2 — Partir edge vs reportes

- Extraer cliente ISAPI + sync a un módulo/proceso `edge`.
- Reportes leen solo de store local de eventos (SQLite/Postgres local).
- Verificar que “generar reporte del día” funciona **sin** llamar ISAPI en ese request.

### Fase 3 — Cola + cursor + reintentos

- Si INTEGRADO no responde: eventos quedan en cola local.
- Reintentos con backoff; misma `external_event_id`.
- Heartbeat independiente del ingest.

### Fase 4 — Cliente “cloud mock”

- Implementar enroll/ingest/heartbeat contra un mock HTTP local (p. ej. otra app FastAPI mínima o `httpbin` + logs).
- Variables de entorno: `INTEGRADO_BASE_URL`, `ENROLLMENT_TOKEN` / `AGENT_CREDENTIAL`.

### Fase 5 — Empaquetado instalable por sede

- Un artefacto (Docker Compose, servicio Windows, o binario) con `.env.example`.
- README de instalación para TI de sede (1–2 páginas).
- Versión semver visible en heartbeat.

### Fase 6 — Entrega a INTEGRADO

Entregar:

1. Código edge + docs de instalación.  
2. Código/UI de reportes + admin (o especificación clara de pantallas).  
3. Este contrato de ingest respetado (o OpenAPI/Swagger del mock).  
4. Mapeo persona → `employee_code` documentado.  
5. Lista de sedes piloto y dispositivos de prueba.

El equipo INTEGRADO se encargará de: manifiesto, `seed_roles`, nginx, schema PostgreSQL, JWT guards, shell UI estándar, Hermes, deploy labs/prod.

---

## 10. Consideraciones técnicas ISAPI (multi-dispositivo)

- **No** consultar todos los dispositivos en serie bloqueante en un solo request HTTP de usuario; el edge trabaja en background.
- Timeouts cortos por dispositivo; un terminal colgado no debe frenar la sede entera.
- Deduplicar marcajes repetidos en ventana corta (mismo person + device + segundos).
- Zona horaria: normalizar a offset/`America/Caracas` antes de ingest.
- Credenciales: un secreto por dispositivo o plantilla por sede; nunca en git; rotación documentada.
- Si el descubrimiento depende de un servicio Windows del fabricante, **debe instalarse en el mismo host del agente** de esa sede.
- Volumen: preferir sync incremental (desde último cursor) cada 1–5 minutos; no full dump diario salvo recuperación.

---

## 11. Consideraciones de seguridad

- Edge: mínimo privilegio de red (solo LAN de biometrías + HTTPS a INTEGRADO).
- No abrir puertos ISAPI al WAN.
- Agent credential rotatorio; enrollment token de corta vida.
- Logs sin passwords ni huellas/templates biométricos.
- Cloud: ingest solo con credencial de agente; reportes solo con JWT + rol.
- Separar ambientes: lab INTEGRADO (`:8090` oficina) vs prod; el edge de producción no debe apuntar a lab por error (URL en `.env` por sede).

---

## 12. Qué hará INTEGRADO al integrar (para que no lo reimplementes)

El monorepo Albatros INTEGRADO ya opera con:

- Un IdP JWT; microservicios solo validan firma/`app_roles`
- Una BD `albatros_core_db` multi-schema (el módulo tendrá schema propio, p. ej. `attendance`)
- Manifiesto `albatros.app.manifest.json` + `seed_roles.py`
- UI shell portal (Hub, tokens CSS) — skill de diseño unificado
- Hermes para correos/alertas
- Deploy labs (casero/oficina) y prod documentados

**No hace falta** que crees un segundo login, ni SMTP propio, ni una BD silo distinta, ni un tema visual aparte.

Referencias internas (equipo portal): estándar de integración Albatros, kit `kit-integracion-albatros/`, skills de roles/UI. El antiguo kit OpenAPI HikCentral queda **histórico**; no seguirlo para producto.

---

## 13. Anti-patrones (evitar)

| Evitar | Por qué |
|--------|---------|
| Un solo agente “central” que VPN a todas las sedes | Frágil, latencia, SPOF, pesadilla de firewall |
| Llamar ISAPI desde el frontend web en cloud | IPs privadas inaccesibles; secretos expuestos |
| Reportes solo en vivo contra dispositivos | Sin datos si cae un terminal o el enlace |
| OpenAPI “por si luego hay licencia” en el mismo código crítico | Camino cerrado; ensucia el diseño |
| Duplicar todo el padrón de empleados en la app | GTH es maestro |
| Hardcodear franjas de una sola oficina | Multi-sede desde el día 1 en config |

---

## 14. Checklist de preparación (antes de pedir integración)

- [ ] OpenAPI HikCentral eliminado o aislado (no en el camino feliz)  
- [ ] `site_id` en dispositivos y eventos  
- [ ] Módulo edge separable (ISAPI + sync + cola)  
- [ ] Reportes leen solo store de eventos  
- [ ] `external_event_id` estable e idempotente  
- [ ] Cliente mock enroll / ingest / heartbeat  
- [ ] UI puede simular roles `admin` / `gth` / `servicios_generales`  
- [ ] Filtro por sede en reportes  
- [ ] `.env.example` del agente documentado  
- [ ] README instalación por sede  
- [ ] Documentados endpoints ISAPI reales usados  
- [ ] Clarificado dependencia (sí/no) de software Hikvision para discovery  
- [ ] Mapeo persona → código empleado documentado  
- [ ] Prueba: cola local sobrevive a “cloud caído” 1 h y luego sync sin duplicar  

---

## 15. Entregables sugeridos al equipo INTEGRADO

1. Repositorio o ZIP con `edge/` + `cloud-app/` (o monorepo interno claro).  
2. Esta guía leída y checklist §14 marcado.  
3. Capturas o video corto: alta dispositivo + reporte del día en una sede.  
4. Ejemplo real de JSON de ingest (anonimizado).  
5. Lista de sedes objetivo y orden de piloto (recomendado: sede donde hoy ya es funcional → luego expansión).

---

## 16. Glosario breve

| Término | Significado |
|---------|-------------|
| ISAPI | API HTTP nativa del dispositivo Hikvision |
| Edge / agente | Servicio en la LAN de una sede |
| Sede / site | Oficina geográfica con su propio agente |
| Ingest | Envío de eventos normalizados a cloud |
| Enrollment | Registro del agente en una sede nueva |
| GTH | Gestión de talento humano en INTEGRADO (maestro personas) |
| Hermes | Bus de notificaciones del ecosistema INTEGRADO |

---

## 17. Contacto de integración portal

Cuando el paquete esté listo según §14–§15, coordinar entrega con el integrador del monorepo INTEGRADO para manifiesto, DDL, nginx, roles y deploy en lab antes de producción.

---

*Documento de arquitectura e integración — Julio J. Valor P. — julio.valor@goalbatros.com · jpvalor1@gmail.com · [CREDITS.md](../../CREDITS.md)*
