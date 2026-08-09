# Instalación del agente edge por sede

**Una instalación = una sede** (Maiquetía, Maracay, etc.). No intente alcanzar IPs de otra ciudad desde un solo PC.

## ¿Debe correr en el mismo PC que el software Hikvision?

**No.** El agente Albatros **no depende** de iVMS / Hik-Connect / “software de servidor” Hikvision.

| Requisito real | Detalle |
|----------------|---------|
| Misma **LAN** (o L2/L3) que los relojes | Debe poder abrir HTTP Digest ISAPI a `IP:80` del terminal |
| Salida hacia INTEGRADO | `INTEGRADO_BASE_URL` (lab `:8090` o prod HTTPS) |
| Credenciales ISAPI | Usuario/clave del **terminal**, no del PC Windows |

El software Hikvision en Windows solo hace falta si TI lo usa para **enrolar caras/huellas en el reloj**. Eso es independiente del agente.

### Raspberry Pi / Linux (plan futuro — factible)

Sí es viable y encaja mejor que Windows:

- Mismo compose: `modulos/biometrico/docker-compose.edge-sede.yml`
- Raspberry Pi 4/5 (aarch64) con Docker + Compose
- Cable Ethernet a la VLAN/LAN de los biométricos
- Consola solo en LAN: `http://IP-DEL-PI:8003/` + `EDGE_ADMIN_PASSWORD`
- El portal INTEGRADO sigue en otra máquina; el Pi solo envía heartbeat/ingest

Limitaciones a validar en PoC: CPU del Pi ante muchos terminales; descubrimiento de red (mejor Ethernet fija que Wi‑Fi).

## Separación de entornos (canónico)

| Componente | Dónde | URL típica |
|------------|--------|------------|
| Portal + reportes | Lab `192.168.105.17` / prod | `:8090/biometrico/` — **solo lectura** de dispositivos |
| Agente + consola | PC sede `192.168.10.31`, Pi, mini-PC Linux | `:8003/` — detectar/configurar |

El contenedor `biometrico-edge` **no** debe publicarse en el compose del portal (`profiles: biometrico-edge-lab` solo para UAT excepcional).

## Checklist TI

- [ ] Terminales en la LAN local, IPs conocidas o descubribles
- [ ] Usuario/clave ISAPI por dispositivo
- [ ] NTP / hora correcta en terminales y en el host del agente
- [ ] Salida HTTP/HTTPS del host hacia INTEGRADO (firewall)
- [ ] (Opcional) Tailscale en ese host para soporte remoto
- [ ] Software Hikvision **solo** si hace falta alta de personas en el terminal
- [ ] `EDGE_ADMIN_PASSWORD` definido (no dejar consola abierta)

## Instalación con Docker (Windows / Linux / Raspberry Pi)

En el **equipo de sede** (no en el servidor del portal):

```bash
# Copiar carpeta modulos/biometrico (o clonar monorepo) al host de sede
cd modulos/biometrico
cp .env.edge-sede.example .env
# Editar .env: INTEGRADO_BASE_URL, ENROLLMENT_TOKEN, EDGE_ADMIN_PASSWORD, ISAPI...

docker compose -f docker-compose.edge-sede.yml --env-file .env up -d --build
```

Abrir consola: `http://IP-DE-ESE-HOST:8003/`

1. Login de consola (`EDGE_ADMIN_*`)
2. Guardar clave ISAPI del reloj
3. Detectar / Agregar / Configurar dispositivos
4. Verificar en el Hub INTEGRADO → Dispositivos (inventario por heartbeat)

Token de enrollment (lab): el mismo `BIOMETRICO_ENROLLMENT_TOKEN` del `.env` del portal, o el que genere ops/script.

## Windows `192.168.10.31` (estado lab)

| Campo | Valor |
|-------|-------|
| Hostname | `VE-TS-SRV-BIO2` / `ve-ts-srv-bio2.albatrosair.local` |
| SSH | `jvalor@192.168.10.31` |
| Llave | `~/.ssh/id_ed25519_albatros_oficina` (misma que lab oficina; instalada en etapa Antigravity) |
| Ping | Suele fallar (ICMP bloqueado); usar SSH/HTTP para probar |
| Agente | `C:\AlbatrosEdge` · servicio WinSW `albatros-edge` · puerto **8003** |
| También en host | Web Client Hikvision en `:80`/`:443` |

```bash
ssh -i ~/.ssh/id_ed25519_albatros_oficina -o IdentitiesOnly=yes jvalor@192.168.10.31
```

### Despliegue consola (2026-08-06)

- Código edge + consola UI actualizados en `C:\AlbatrosEdge\backend`.
- Servicio `Albatros Edge Service` reinstalado/arrancado (WinSW).
- Login consola: usuario `admin` + `EDGE_ADMIN_PASSWORD` (en `C:\AlbatrosEdge\backend\.env`; no en git).
- Si `http://192.168.10.31:8003/` no abre desde otra VLAN, usar túnel:

```bash
ssh -i ~/.ssh/id_ed25519_albatros_oficina -o IdentitiesOnly=yes \
  -L 18003:127.0.0.1:8003 jvalor@192.168.10.31
# luego: http://127.0.0.1:18003/
```

En el lab portal: **no** levantar perfil `biometrico-edge-lab` (evitar dos agentes).  
Plan futuro preferido: Raspberry Pi / Linux dedicado en la misma LAN.

## Prohibido

- Exponer ISAPI a Internet
- Un solo agente “central” con VPN a todas las sedes como diseño principal
- Guardar passwords ISAPI en cloud / git
- Publicar la consola `:8003` en el servidor del portal INTEGRADO como solución definitiva
