# Instalación del agente edge por sede

**Una instalación = una sede** (Maiquetía, Maracay, etc.). No intente alcanzar IPs de otra ciudad desde un solo PC.

## Checklist TI

- [ ] Terminales en la LAN local, IPs conocidas o descubribles
- [ ] Usuario/clave ISAPI por dispositivo
- [ ] NTP / hora correcta en terminales y en el PC del agente
- [ ] Salida HTTPS del PC hacia INTEGRADO (firewall)
- [ ] (Opcional) Tailscale en ese PC para soporte
- [ ] Software Hikvision de configuración solo si lo necesita el alta de personas

## Pasos

1. Admin en portal crea sede → recibe `enrollment_token` (en lab: `POST /api/asistencia/v1/lab/issue-enrollment`).
2. En la oficina, copie el código del módulo y cree `backend/.env` desde `.env.example`.
3. Configure:
   - `SITE_CODE` / `SITE_NAME`
   - `SOURCE=hikvision`
   - `HIKVISION_DEVICES=...`
   - `HIKVISION_USER` / `HIKVISION_PASSWORD`
   - `INTEGRADO_BASE_URL` (prod/lab) + `ENROLLMENT_TOKEN`
4. Arranque el backend (`uvicorn` puerto acordado) y ejecute enroll:
   - `POST /api/biometrico/edge/enroll` (guarda `AGENT_CREDENTIAL` en `.env`).
5. Alta dispositivos en UI **Dispositivos** (solo en LAN).
6. Sync periódico: `POST /api/biometrico/edge/sync` (+ `push_to_cloud=true`) o tarea programada.
7. Heartbeat: `POST /api/biometrico/edge/heartbeat`.

## Prohibido

- Exponer ISAPI a Internet
- Un solo agente “central” con VPN a todas las sedes como diseño principal
- Guardar passwords ISAPI en cloud / git
