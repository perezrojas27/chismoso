# Endpoints ISAPI usados (DS-K1T8003MF)

Auth: **HTTP Digest** (`HIKVISION_USER` / `HIKVISION_PASSWORD`).  
No se usa OpenAPI / Artemis de HikCentral.

| Uso | Método | Path | Notas |
|-----|--------|------|-------|
| Info dispositivo | GET | `/ISAPI/System/deviceInfo` | Probe / health |
| Eventos de acceso | POST | `/ISAPI/AccessControl/AcsEvent?format=json` | Preferido; paginación `searchResultPosition` + `maxResults` (firmware ≤ 10) |
| Eventos (XML legacy) | POST | `/ISAPI/AccessControl/AcsEvent/Search` | Fallback |
| Usuarios | POST | `/ISAPI/AccessControl/UserInfo/Search?format=json` | Enriquece nombre por `employeeNo` (lotes ≤ 10) |

## Descubrimiento de dispositivos

Hoy: probe HTTP en LAN / alta manual por IP (UI Dispositivos).  
No depende de SADP obligatorio; si TI usa herramientas Hikvision, deben correr **en el mismo host del agente** de esa sede.

## Secretos

Viven solo en el edge (`.env` / secret store local). Cloud recibe eventos normalizados, nunca la clave ISAPI.
