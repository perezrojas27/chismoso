# Estado actual y pendientes — Biométricos (Agosto 2026)

Documento vivo del módulo. Canónico monorepo: [`docs/modulos/MODULO_BIOMETRICO.md`](../../../docs/modulos/MODULO_BIOMETRICO.md).

## Hecho

- Refactor `edge_app` / `cloud_app` / `shared` + asimilación a INTEGRADO (`client_id=biometrico`).
- Cloud + SPA en lab oficina (`:8090`); inventarios vía heartbeat.
- **Consola de sede** en el agente (`:8003`): login TI, ISAPI, detectar/configurar dispositivos.
- Separación: edge **no** se publica en el compose del portal (perfil `biometrico-edge-lab` opcional).
- Windows `192.168.10.31`: `C:\AlbatrosEdge` + WinSW; SSH `jvalor` + llave oficina.
- Compose independiente: `docker-compose.edge-sede.yml` (Linux/Pi).
- Diagnóstico inestabilidad BIO2: `scripts/diag-biometricos-bio2.sh`.

## Pendiente

1. Asignar roles a grupos en Admin.
2. UAT marcajes / comedor / PDF con agente sede estable.
3. Firewall `:8003` entre VLANs **o** acceso solo por túnel SSH / host en misma LAN.
4. PoC Raspberry Pi como agente (recomendado vs Windows HikCentral).
5. Deploy prod — solo tras UAT.

## Notas de inestabilidad BIO2

El host `.31` ejecuta **HikCentral Access Control** completo en ~8 GB RAM; hay cortes de ruta y crash loops históricos del servicio edge. No usar ping ICMP como único criterio (bloqueado). Ver [`DIAGNOSTICO_INESTABILIDAD_BIO2_20260806.md`](../../../docs/informes/DIAGNOSTICO_INESTABILIDAD_BIO2_20260806.md).

---

*Integración documentada por Julio J. Valor P. — julio.valor@goalbatros.com · jpvalor1@gmail.com · [CREDITS.md](../../../CREDITS.md)*
