# Packaging — cliente local (agente edge + consola)

El **cliente de sede** ya vive en este repo:

| Pieza | Ruta |
|-------|------|
| API + consola web | `backend/edge_app/` (`console/` = UI en `:8003`) |
| Config compartida | `backend/shared/` |
| Servicio Windows (WinSW) | `albatros-edge.xml` · scripts en `packaging/windows/` |
| Docker multiplataforma | `docker-compose.edge-sede.yml` |
| Linux Debian (systemd) | `packaging/debian/` |

**No** es la SPA de reportes del portal (`frontend/`). Esa corre en INTEGRADO.

## Tamaños aproximados

| Entrega | Peso orientativo |
|---------|------------------|
| Código fuente edge (sin `.git`, sin venv) | **~1–2 MB** |
| Zip/tar de instalación (código + scripts, sin Python) | **~2–3 MB** |
| Instalado Windows/Linux con venv + `requirements-edge.txt` | **~90–150 MB** |
| Imagen Docker `python:3.11-slim` + deps | **~250–400 MB** |
| WinSW `WinSW-x64.exe` (descarga aparte) | **~0,5 MB** |

El peso grande es el **runtime Python + librerías**, no la consola HTML.

## Guías

- Instrucciones unificadas: [`docs/INSTALACION_CLIENTE_EDGE.md`](../docs/INSTALACION_CLIENTE_EDGE.md)
- Contexto sede / red: [`docs/INSTALACION_AGENTE_SEDE.md`](../docs/INSTALACION_AGENTE_SEDE.md)

## Scripts

```bash
# Windows (PowerShell como Administrador, en el PC de sede)
.\packaging\windows\install-edge.ps1 -RepoRoot .

# Debian 12+
sudo bash packaging/debian/install-edge-debian.sh

# O Docker (Windows / Debian / Pi)
cp .env.edge-sede.example .env   # editar
docker compose -f docker-compose.edge-sede.yml --env-file .env up -d --build
```
