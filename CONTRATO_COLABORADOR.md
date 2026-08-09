# Contrato colaborador — Albatros Biométrico

**Fecha:** 2026-08-08  
**Repo producto:** [`perezrojas27/chismoso`](https://github.com/perezrojas27/chismoso)  
**Embebido / deploy:** monorepo Albatros INTEGRADO → `modulos/biometrico/`

## Quién hace qué

| Rol | Trabaja en | Responsabilidad |
|-----|------------|-----------------|
| **Colaborador** | chismoso | ISAPI, agente edge, consola sede, reportes, UI del módulo |
| **Integrador** | INTEGRADO | Importar cambios, nginx, compose, `seed_roles`, Hub, labs/prod |

No hace falta clonar ni entender todo INTEGRADO para desarrollar features de biométrico.

## Flujo

```
chismoso (colaborador) ──PR/rama──► import a modulos/biometrico/ ──► deploy lab
INTEGRADO (código vivo portal) ──export puntual──► chismoso (como 2026-08-08)
```

## Puedes cambiar (en chismoso)

- `backend/edge_app/` (ISAPI, sync, consola, dispositivos)
- `backend/cloud_app/` (reportes, ingest, excepciones, vínculo GTH)
- `backend/shared/` (lógica compartida; cuidado con JWT/DB)
- `frontend/` (SPA del módulo)
- `docs/` de este módulo
- `docker-compose.edge-sede.yml`, `deploy.bat`, packaging Windows del agente

## No cambies sin avisar al integrador

- `client_id` o nombres de roles (`servicios_generales`, `gth`, `admin`)
- Secretos reales (`.env`, passwords ISAPI, `JWT_SECRET_KEY`, tokens de enroll)
- Asumir rutas del portal distintas a `/biometrico/` y `/api/biometrico/` / `/api/asistencia/v1/`
- Commits con credenciales o dumps de BD

Los roles y el manifiesto deben reflejarse también en el monorepo (`seed_roles` + Hub); eso lo cierra el integrador al importar.

## Prohibido

- Commitear `.env`, `.env.deploy`, passwords ISAPI.
- Asumir que el Hub “escanea” la LAN: el portal solo muestra lo que el agente reporta por heartbeat/ingest.

## Lab local vs portal

| | Lab (chismoso) | Portal INTEGRADO |
|--|----------------|------------------|
| Auth | `AUTH_DISABLED=true` | JWT IdP |
| Datos reportes | SQLite / mock | Postgres schema `biometrico` |
| UI | `npm run dev :5173` | `/biometrico/` detrás de nginx |
| Consola dispositivos | Edge `:8003` | Misma idea en la sede, no en el Hub |

## Referencia embebido

- `README_INTEGRADO.md` — notas de empaquetado (Dockerfiles, nginx del módulo)
- Monorepo: `docs/guias/HANDOFF_BIOMETRICO_INTEGRADO_20260806.md`

---

*Integración y contrato — Julio J. Valor P. · julio.valor@goalbatros.com · jpvalor1@gmail.com*
