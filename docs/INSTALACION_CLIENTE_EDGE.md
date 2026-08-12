# Instalación del cliente local — Albatros Edge (consola biométricos)

**Qué es:** agente de **sede** + consola web en el puerto **8003** (detectar/editar/probar relojes ISAPI).  
**Qué no es:** la SPA de reportes del Hub INTEGRADO (`/biometrico/`).

El código del cliente **ya está** en este repo (`backend/edge_app/` + `backend/shared/`).  
Los instaladores están en [`packaging/`](../packaging/README.md).

---

## Tamaños (orientativos)

| Qué | Peso |
|-----|------|
| Solo código del cliente (edge + shared + packaging) | **~1–2 MB** |
| Tras instalar con venv (`requirements-edge.txt`) | **~90–150 MB** en disco |
| Opción Docker (imagen + capas) | **~250–400 MB** |

El grueso es Python + librerías (FastAPI, httpx, etc.), no la UI HTML de la consola.

---

## Requisitos comunes

- Misma LAN (o L2/L3) que los relojes Hikvision  
- Salida HTTP/HTTPS hacia el portal INTEGRADO  
- **No** hace falta iVMS/HikCentral en la misma máquina  
- Definir `EDGE_ADMIN_PASSWORD` (consola) y credenciales ISAPI (reloj)  
- Firewall: `:8003` solo LAN TI / sede — **nunca** a Internet  

Plantilla de variables: [`.env.edge-sede.example`](../.env.edge-sede.example).

---

## Opción A — Windows (servicio WinSW)

1. Instalar [Python 3.11+](https://www.python.org/downloads/) (marcar “Add to PATH”).  
2. Clonar o copiar este repo al PC de sede.  
3. PowerShell **como Administrador**:

```powershell
cd Ruta\AlbatrosBiometrico
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\windows\install-edge.ps1 -RepoRoot .
```

4. Editar `C:\AlbatrosEdge\backend\.env`  
   (`INTEGRADO_BASE_URL`, `ENROLLMENT_TOKEN`, `EDGE_ADMIN_PASSWORD`, ISAPI…).  
5. Reiniciar servicio si cambió el `.env`:

```powershell
Restart-Service albatros-edge
```

6. Abrir **http://127.0.0.1:8003/** (o `http://IP-DEL-PC:8003/` desde la LAN).

Desinstalar:

```powershell
.\packaging\windows\uninstall-edge.ps1
# o con borrado: .\packaging\windows\uninstall-edge.ps1 -RemoveFiles
```

Lab actual: `C:\AlbatrosEdge` en `192.168.10.31` (BIO2). Detalle de red: [`INSTALACION_AGENTE_SEDE.md`](INSTALACION_AGENTE_SEDE.md).

---

## Opción B — Debian 12+ (systemd)

Recomendado para mini-PC / Raspberry Pi con Debian (o Raspberry Pi OS basado en Debian).

```bash
# En el equipo de sede, con el repo clonado:
cd /ruta/Albatros-Biometrico
sudo bash packaging/debian/install-edge-debian.sh

# Editar configuración:
sudo nano /opt/albatros-edge/backend/.env
sudo systemctl restart albatros-edge

# Consola:
# http://127.0.0.1:8003/
```

Variables útiles:

| Variable | Default |
|----------|---------|
| `ALBATROS_EDGE_HOME` | `/opt/albatros-edge` |
| `ALBATROS_EDGE_USER` | `albatros-edge` |
| `BIOMETRICO_EDGE_PORT` | `8003` |

```bash
sudo systemctl status albatros-edge
sudo journalctl -u albatros-edge -f
```

Desinstalar:

```bash
sudo bash packaging/debian/uninstall-edge-debian.sh
# borrar datos:
sudo REMOVE_FILES=1 bash packaging/debian/uninstall-edge-debian.sh
```

---

## Opción C — Docker (Windows / Debian / Pi)

Útil si ya usan Docker en sede:

```bash
cd /ruta/Albatros-Biometrico
cp .env.edge-sede.example .env
# editar .env
docker compose -f docker-compose.edge-sede.yml --env-file .env up -d --build
```

Consola: `http://IP-DEL-HOST:8003/`

---

## Primer uso de la consola

1. Login (`EDGE_ADMIN_USER` / `EDGE_ADMIN_PASSWORD`)  
2. Guardar **clave ISAPI del reloj** (no confundir con la de la consola)  
3. Detectar / Agregar / **Editar** / **Probar** dispositivos  
4. Verificar en Hub INTEGRADO → Control de Biométricos → Dispositivos (heartbeat)

---

## Relación con INTEGRADO (desacoplado)

| Capa | Dónde |
|------|--------|
| Cliente edge + consola | Este repo → PC/Pi de **sede** |
| Reportes / Hub | Monorepo INTEGRADO (`modulos/biometrico` cloud + SPA) |

Contrato: [`CONTRATO_COLABORADOR.md`](../CONTRATO_COLABORADOR.md).

---

*Actualizado 2026-08-12*
