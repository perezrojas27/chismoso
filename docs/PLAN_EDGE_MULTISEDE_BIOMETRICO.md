# Plan — Edge biométrico multi-sede (reporte a INTEGRADO fuera de LAN)

**Fecha:** 2026-08-12  
**Módulo:** `client_id=biometrico`  
**Prod:** no ejecutar aún — labs oficina `:8090` / casero `:8080` / Tailscale.  
**Relacionado:** [`VINCULO_GTH_BIOMETRICO.md`](VINCULO_GTH_BIOMETRICO.md) · [`modulos/biometrico/docs/INSTALACION_AGENTE_SEDE.md`](../../modulos/biometrico/docs/INSTALACION_AGENTE_SEDE.md) · consola edge

---

## 1. Principio

| Pieza | Dónde vive | Red |
|-------|------------|-----|
| Relojes Hikvision | LAN de la **sucursal** | Solo hablan con el agente local (ISAPI) |
| Agente edge | PC/Pi/minipc **en la sede** | LAN a relojes + salida a INTEGRADO |
| Cloud biométrico | Portal INTEGRADO | Recibe enroll, heartbeat e ingest |

**Un proceso edge = una sede geográfica** (`SITE_CODE` / `SITE_NAME`).  
Los relojes **no** se publican a internet.

```text
[Relojes sede] --LAN/ISAPI--> [Agente edge] --Tailscale o HTTPS--> [INTEGRADO cloud]
                                      |
                                      +-- Consola local :8003 (solo sede)
```

---

## 2. Identidad de sede

| Campo | Uso |
|-------|-----|
| `SITE_CODE` | Código estable (`oficina_central`, `valencia_norte`, …) — va en heartbeat/enroll |
| `SITE_NAME` | Etiqueta humana |
| `biometrico.site_map` | Cruce `biometric_site_id` ↔ `core.sites` (GTH) para presencia |
| Ubicación del reloj | Texto libre en el agente (piso, puerta); **no** sustituye `SITE_CODE` |

Default de fábrica `oficina_central` es solo lab; **cada sucursal nueva debe cambiarlo** (consola edge o `.env`) antes de enroll productivo.

---

## 3. Transporte a INTEGRADO (fuera de LAN)

### Labs (recomendado hoy)

**Tailscale** entre nodo de sede y lab UAT (`srv-pruebas-oficina` / casero):

- `INTEGRADO_BASE_URL=http://srv-pruebas-oficina:8090` (o IP Tailscale del lab)
- Relojes siguen en `192.168.x.x` locales; el edge usa la LAN local para ISAPI
- No abrir puertos ISAPI al WAN

### Producción (futuro; no ahora)

- `INTEGRADO_BASE_URL=https://integrado.goalbatros.com`
- Agente autenticado con **credential / enrollment token** (nunca credenciales ISAPI en el cloud)
- TLS obligatorio; sin exponer `:8003` ni relojes a Internet

### Anti-patrones

- Reloj con IP/port públicos  
- Un solo edge “sirviendo” varias sedes geográficas  
- Dejar `SITE_CODE=oficina_central` en todas las sucursales  
- Sync BD lab → prod  

---

## 4. Enrolamiento por sucursal

1. Crear sede en GTH (`core.sites`) si no existe.  
2. En lab/Admin biométrico (o API): emitir **enrollment token** ligado a `site_code`.  
3. En el agente: fijar `SITE_CODE` / `SITE_NAME` (consola o `.env`).  
4. Configurar `INTEGRADO_BASE_URL` + token; arrancar edge → enroll → heartbeat.  
5. Insertar fila en `biometrico.site_map` (sede edge ↔ UUID `core.sites`).  
6. Smoke: Hub → Dispositivos muestra **Sede agente** correcta; marcajes llegan con ese `site_id`.

---

## 5. Checklist por sucursal

```text
Sucursal: _____________  SITE_CODE: _____________
Hardware edge: [ ] Pi  [ ] PC Windows  [ ] otro
[ ] SITE_CODE / SITE_NAME únicos (consola o .env)
[ ] Clave consola edge (EDGE_ADMIN_*)
[ ] Credenciales ISAPI de relojes (solo en el agente)
[ ] INTEGRADO_BASE_URL alcanzable (Tailscale lab / HTTPS prod futuro)
[ ] Enrollment token aplicado; heartbeat OK
[ ] Relojes en inventario local + reportados a cloud
[ ] biometrico.site_map ↔ core.sites
[ ] Vínculos GTH de personal de esa sede (muestra)
[ ] Smoke: Asistencia / Comedor / Dispositivos en Hub
[ ] Prod: N/A hasta autorización explícita
```

---

## 6. Roadmap técnico (labs)

| Fase | Entregable | Estado |
|------|------------|--------|
| A | Doc este plan | ✅ 2026-08-12 |
| B | Consola edge: editar sede; cloud Distingue sede vs ubicación reloj | en curso |
| C | UX vínculo GTH (filtros independientes + confirmación) | en curso |
| D | Select sedes GTH en presencia (catálogo) | en curso |
| E | Pack Pi/Windows documentado por sede (instaladores ya en `packaging/`) | checklist |
| F | Prod HTTPS + rotación tokens | futuro |

---

## Historial

| Fecha | Nota |
|-------|------|
| 2026-08-12 | Borrador operativo: Tailscale labs, un edge/sede, sin ISAPI a Internet |
