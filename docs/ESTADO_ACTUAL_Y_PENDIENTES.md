# Estado Actual y Tareas Pendientes (Agosto 2026)

## Contexto de la Sesión
- Se refactorizó el código original (monolito en `backend/app`) dividiéndolo en tres subpaquetes lógicos: `edge_app`, `cloud_app` y `shared`.
- **Despliegue Edge Finalizado**: El Agente Edge fue instalado exitosamente en el servidor de Biométricos (Windows 10 - `192.168.10.31`).
  - Se instaló Python 3.11 en el entorno de Windows.
  - Se configuró la conexión local al terminal físico (IP: 192.168.10.200).
  - Se utilizó WinSW para convertir la aplicación en el **Servicio de Windows** `Albatros Edge Service`, garantizando su ejecución en segundo plano (puerto 8003).
- **Documentación de Integración**: Se redactó el documento `GUIA_INTEGRACION_INTEGRADO.md` con las especificaciones técnicas para que el equipo de desarrollo asimile el módulo biométrico en el ERP principal.

## Pendientes para la Siguiente Etapa (Proyecto INTEGRADO)

1. **Asimilación en INTEGRADO:**
   - Crear los roles sugeridos (`biometricos.view`, `biometricos.admin`, `biometricos.system`) en el módulo de Auth/Permisos.
   - Apuntar el `cloud_app` a la base de datos PostgreSQL de INTEGRADO (`albatros-db`) y correr las migraciones (Alembic) para generar las tablas.

2. **Despliegue del Cloud App en Servidor de Pruebas:**
   - En el servidor de pruebas (`192.168.105.17`), modificar el archivo `docker-compose.server.yml` de INTEGRADO para agregar el servicio `biometricos-cloud`.
   - Exponer el puerto `8090` para recibir la ingesta de datos proveniente del Agente Edge instalado en Windows.

3. **Pruebas de Ingesta Reales:**
   - Verificar que los eventos marcados en el biométrico fluyan correctamente desde el `edge_app` hacia el `biometricos-cloud` y se registren en la base de datos de PostgreSQL.

4. **Desarrollo Frontend:**
   - Consumir la API desde el Frontend en React/Vue para mostrar los reportes de asistencia y generar las exportaciones de PDF/Excel.
