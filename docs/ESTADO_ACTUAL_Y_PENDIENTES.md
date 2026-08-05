# Estado Actual y Tareas Pendientes (Agosto 2026)

## Contexto de la Sesión
- Se refactorizó el código original (monolito en `backend/app`) dividiéndolo en tres subpaquetes lógicos para reflejar la arquitectura requerida:
  1. `edge_app`: Código específico para las sedes físicas (Conector ISAPI, SQLite local).
  2. `cloud_app`: Código centralizado (generación de reportes PDF, lógica de mock).
  3. `shared`: Modelos, configuraciones y utilidades compartidas.
- **Entorno Local**: Se comprobó que el código es 100% compatible con Windows y Linux (`pathlib`). En Fedora es necesario tener `gcc` y `python3-devel` instalados para compilar módulos como `pydantic-core`. Se documentó esto en el `README.md`.
- **Proyecto INTEGRADO**: Se analizó el entorno de prueba del proyecto principal de login. El agente de Edge enviará los datos locales al servidor Hestia de pruebas ubicado en la IP `http://192.168.105.17:8090`.

## Pendientes para la Siguiente Sesión
1. **Acceso al Servidor de Biométricos (Windows 10 - 192.168.10.31):**
   - El administrador de red debe finalizar de habilitar OpenSSH Server e inyectar la llave pública (`id_ed25519_albatros_oficina.pub`).
   - Obtener el nombre de usuario (username) para conectarse por SSH.
2. **Empaquetado y Despliegue del Agente Edge:**
   - Crear el archivo `.env` apuntando a `INTEGRADO_BASE_URL=http://192.168.105.17:8090`.
   - Transferir los archivos del subpaquete `edge_app` (y `shared`) a la máquina Windows.
   - Crear un script `.bat` o `.ps1` que instale las dependencias de Python de forma local en la máquina de biométricos.
   - Configurar `edge_app/main.py` como un Servicio de Windows usando herramientas como NSSM (Non-Sucking Service Manager) o `win32serviceutil` para asegurar que siempre corra de fondo sin depender de sesión de usuario, ya que HikCentral corre en la misma máquina en los puertos 80/443.
3. **Pruebas de Ingesta:**
   - Confirmar que el Agente Edge pueda hablar exitosamente por ISAPI con el biométrico.
   - Verificar la subida de los eventos marcados hacia la ruta de mock/ingesta en el servidor de pruebas (`192.168.105.17:8090`).
