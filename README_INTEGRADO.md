# Control de Biométricos — módulo en monorepo INTEGRADO

**Workspace colaborador:** [`perezrojas27/chismoso`](https://github.com/perezrojas27/chismoso) (export vivo 2026-08-08).  
**Contrato dual-repo:** [`CONTRATO_COLABORADOR.md`](CONTRATO_COLABORADOR.md)  
**Docs monorepo:** [`docs/modulos/MODULO_BIOMETRICO.md`](../../docs/modulos/MODULO_BIOMETRICO.md) · [`docs/guias/HANDOFF_BIOMETRICO_INTEGRADO_20260806.md`](../../docs/guias/HANDOFF_BIOMETRICO_INTEGRADO_20260806.md)

## Decisiones

| # | Tema | Decisión |
|---|------|---------|
| 1 | Marcajes | ISAPI + agente edge por sede |
| 2 | Roles | `biometrico` · `servicios_generales`, `gth`, `admin` |
| 3 | Cloud | Postgres schema `biometrico` |
| 4 | Entornos | Portal = reportes; sede = consola `:8003` |
| 5 | UI portal | Shell admin INTEGRADO |
| 6 | Futuro | Preferir Raspberry Pi / Linux en LAN relojes (no depender de Windows HikCentral) |

## Estructura

| Ruta | Rol |
|------|-----|
| `backend/edge_app/` | Agente + **consola** (`console/`) |
| `backend/cloud_app/` | Ingest + reportes JWT |
| `backend/shared/` | Config, JWT, Postgres |
| `frontend/` | SPA → `/biometrico/` |
| `docker-compose.edge-sede.yml` | Deploy agente fuera del portal |
| `.env.edge-sede.example` | Plantilla agente sede |
| `docs/INSTALACION_AGENTE_SEDE.md` | Windows / Docker / Pi / SSH |

**No versionar:** `backend/.env`, `.env`, `backend/data/`, secretos ISAPI, `frontend/node_modules/`.

---

*Integración documentada por Julio J. Valor P. — julio.valor@goalbatros.com · jpvalor1@gmail.com · [CREDITS.md](../../CREDITS.md)*
