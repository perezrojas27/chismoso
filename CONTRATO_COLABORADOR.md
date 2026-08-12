# Contrato colaborador — Albatros Biométrico

**Actualizado:** 2026-08-12  
**Repo producto:** [`perezrojas27/chismoso`](https://github.com/perezrojas27/chismoso) (clone local: *Albatros Biométrico*)  
**Embebido / deploy:** monorepo Albatros INTEGRADO → `modulos/biometrico/`

## Quién hace qué

| Rol | Trabaja en | Responsabilidad |
|-----|------------|-----------------|
| **Colaborador** | chismoso / Albatros Biométrico | ISAPI, agente edge, consola sede, reportes, UI del módulo |
| **Integrador** | INTEGRADO | Importar cambios, nginx, compose, manifiesto/`seed_roles`, Hub, labs/prod |

No hace falta clonar ni entender todo INTEGRADO para desarrollar features de biométrico.

## Flujo (desacoplado)

```
chismoso (colaborador) ──PR/sync──► modulos/biometrico/ ──► deploy lab INTEGRADO
INTEGRADO (fixes portal) ──export──► chismoso (mantener paridad)
```

| Capa | Repo | Runtime |
|------|------|---------|
| Edge + consola `:8003` | Este repo (`edge_app`) | PC/Pi sede (`C:\AlbatrosEdge` o Docker) |
| Cloud + SPA | Este repo + portal | Labs `:8080`/`:8090` · prod solo con OK |
| Catálogo roles | Manifiesto aquí + Admin Importar manifiesto | IdP INTEGRADO |

## Puedes cambiar (en este repo)

- `backend/edge_app/` (ISAPI, sync, consola, dispositivos, auth consola)
- `backend/cloud_app/` (reportes, ingest, excepciones, vínculo GTH)
- `backend/shared/` (cuidado con JWT/DB)
- `frontend/` (SPA)
- `docs/`, `docker-compose.edge-sede.yml`, `deploy.bat`, packaging Windows

## Consola sede (esperado 2026-08-12)

- Editar dispositivo (IP/puerto/ubicación)
- Probar ISAPI por equipo
- Cambiar usuario/clave de **esta consola** (`data/console_auth.json`)
- Clave ISAPI del reloj (aparte)
- **No** configurar UI del terminal (formato hora 12h/24h, etc.) — fuera de alcance actual

## No cambies sin avisar al integrador

- `client_id` o nombres de roles (`servicios_generales`, `gth`, `admin`)
- Secretos reales (`.env`, passwords ISAPI, `JWT_SECRET_KEY`, tokens de enroll)
- Rutas distintas a `/biometrico/`, `/api/biometrico/`, `/api/asistencia/v1/`
- Commits con credenciales o dumps de BD

## Prohibido

- Commitear `.env`, `.env.deploy`, passwords ISAPI
- Asumir que el Hub escanea la LAN
- Exponer ISAPI a Internet
- Publicar edge en el compose del portal como diseño definitivo

## Lab local vs portal

| | Lab (este repo) | Portal INTEGRADO |
|--|-----------------|------------------|
| Auth | `AUTH_DISABLED=true` | JWT IdP |
| Datos reportes | SQLite / mock | Postgres `biometrico` |
| UI | `npm run dev :5173` | `/biometrico/` |
| Consola dispositivos | Edge `:8003` | Misma idea en la **sede**, no en el Hub |

**Grupos geográficos** del listado HikCentral/biométrico **no** están en INTEGRADO y **no** sustituyen `person_links` — ver `docs/VINCULO_GTH_BIOMETRICO.md`.

## Referencia

- `README.md` · `README_INTEGRADO.md`
- Monorepo: `docs/guias/MANUAL_INTEGRADOR_APLICACIONES.md` · `docs/guias/HANDOFF_BIOMETRICO_INTEGRADO_20260806.md`

---

*Integración y contrato — Julio J. Valor P. · julio.valor@goalbatros.com · jpvalor1@gmail.com*
