# Handoff — Chismoso → INTEGRADO (2026-08-06)

Este repositorio (`perezrojas27/chismoso`) es el **origen** del módulo de asistencia/comedor ISAPI.

## Dónde se desarrolla ahora

**Fuente de verdad:** monorepo [`jpvalor-pololo/INTEGRADO`](https://github.com/jpvalor-pololo/INTEGRADO)

| Antes (chismoso) | Ahora (INTEGRADO) |
|------------------|-------------------|
| Repo standalone | `modulos/biometrico/` |
| Cloud + edge locales | Cloud en compose del portal + edge Docker lab / agente sede |
| Roles preliminares | `client_id=biometrico` · `servicios_generales` · `gth` · `admin` |

Documentación operativa completa en INTEGRADO:

- `docs/guias/HANDOFF_BIOMETRICO_INTEGRADO_20260806.md`
- `docs/modulos/MODULO_BIOMETRICO.md`
- `modulos/biometrico/README_INTEGRADO.md`

## Estado lab (oficina Albatros) — 2026-08-06

- Portal: `http://192.168.105.17:8090/biometrico/`
- Edge Docker en el lab enrollado; heartbeat reporta `PRINCIPAL@192.168.10.200`
- Pendiente ops: `HIKVISION_PASSWORD` para sync ISAPI / PDF reales
- **Prod:** no desplegado

## Para colaboradores

1. Clonar / trabajar en **INTEGRADO**, no añadir features solo aquí.
2. PRs de biométrico van al monorepo (manifiesto, `seed_roles`, nginx, compose).
3. Este repo puede seguir como referencia de packaging Windows (`deploy.bat`, XML edge) si hace falta.

## Prohibido

- Commitear `.env`, `.env.deploy`, passwords ISAPI.
- Asumir que el Hub “escanea” la LAN: el portal solo muestra lo que el agente reporta.

---

*Nota de integración INTEGRADO — Julio J. Valor P. · julio.valor@goalbatros.com · jpvalor1@gmail.com*
