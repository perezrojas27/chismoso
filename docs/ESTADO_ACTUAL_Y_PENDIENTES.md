# Estado actual y pendientes — Biométricos (Agosto 2026)

Documento vivo del módulo en el **repo producto** (chismoso / Albatros Biométrico).  
En el monorepo: `docs/modulos/MODULO_BIOMETRICO.md`.

## Hecho

- Refactor `edge_app` / `cloud_app` / `shared` + `client_id=biometrico`.
- Cloud + SPA en labs INTEGRADO (oficina `:8090`, casero `:8080`).
- **Modelo desacoplado:** edge en sede; portal no es dueño de ISAPI.
- **Consola de sede** (`:8003`): login TI, ISAPI, detectar / **editar** / **probar** / quitar; cambio de clave de consola (`console_auth.json`) — sync 2026-08-12.
- Edge **no** en compose portal por defecto (`biometrico-edge-lab` opcional).
- Windows `192.168.10.31`: `C:\AlbatrosEdge` + WinSW `albatros-edge`.
- Compose independiente: `docker-compose.edge-sede.yml`.
- Vínculo GTH: `person_links` + UI/API.
- Nota: grupos geo del biométrico **no** sincronizados (no sustituyen `person_links`).

## Pendiente

1. Roles biométrico en Grupos (Admin labs) + UAT humano.
2. UAT marcajes / comedor / PDF con agente sede estable.
3. Firewall `:8003` entre VLANs o solo túnel SSH.
4. PoC Raspberry Pi como agente.
5. Auto-vínculo si `employeeNo` ≈ cédula; sync grupos geo (opcional).
6. Deploy prod — solo tras UAT + OK.

## Docs locales

- `ARQUITECTURA_EDGE_CLOUD.md` · `INSTALACION_AGENTE_SEDE.md` · `ISAPI_ENDPOINTS.md`
- `VINCULO_GTH_BIOMETRICO.md` · `GUIA_COLABORADOR_ASISTENCIA_ISAPI_MULTI_SEDE.md`

---

*Actualizado 2026-08-12 — sync desacoplado + consola ampliada*
