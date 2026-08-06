# Guía de Integración: Módulo Biométrico en INTEGRADO

Este documento sirve como hoja de ruta técnica para el equipo de desarrollo de **INTEGRADO**. Su objetivo es detallar cómo asimilar el módulo biométrico (Albatros Biométrico) dentro del ecosistema del ERP, gestionar sus permisos y desplegar la arquitectura Cloud en el servidor de pruebas (`192.168.105.17`).

---

## 1. Arquitectura del Módulo

El sistema se divide en dos componentes principales:
1. **Edge App (Local/Windows 10)**: Ya desplegado en `192.168.10.31` como servicio de Windows. Se encarga de hablar con los terminales Hikvision vía ISAPI, extraer los eventos de asistencia y empujarlos hacia el servidor en la nube.
2. **Cloud App (Central/Debian)**: El componente que vivirá dentro de INTEGRADO. Expone la API central para recibir los datos de todas las sedes, almacena el historial en PostgreSQL y genera los reportes consolidados (PDF/Excel) para Recursos Humanos.

---

## 2. Roles y Permisos (Asimilación en INTEGRADO)

Para integrar este módulo en el sistema de Auth y Roles de INTEGRADO (Hermes/Albatros), se deben crear los siguientes permisos en la base de datos central:

### Permisos Sugeridos:
- `biometricos.view`: Permite a un empleado ver únicamente sus propios marcajes de asistencia y horas trabajadas.
- `biometricos.reports`: Permite a los supervisores de área generar reportes de asistencia de sus subordinados.
- `biometricos.admin`: Permite gestionar los dispositivos físicos (IPs, contraseñas ISAPI) y modificar registros anómalos o justificar faltas.
- `biometricos.system`: Permiso exclusivo de sistema/API. Utilizado por el `Edge App` (usando el `INTEGRADO_API_KEY`) para tener autorización de inyectar registros directamente a la base de datos de INTEGRADO sin interacción humana.

### Flujo de Autenticación:
El `Edge App` enviará los eventos usando un API Key estático o un token JWT de larga duración de máquina a máquina (M2M). Las peticiones irán con el header:
`Authorization: Bearer <API_KEY_SISTEMA>`

---

## 3. Integración a Base de Datos (PostgreSQL)

Actualmente, el código de `cloud_app` utiliza SQLAlchemy. Para asimilarlo en INTEGRADO:
1. Se debe apuntar la variable `DATABASE_URL` del `cloud_app` hacia la instancia de PostgreSQL existente de INTEGRADO (`albatros-db`).
2. Generar las tablas necesarias corriendo las migraciones (Alembic) que crearán `device_events`, `devices`, y `sync_logs`.
3. Establecer relaciones (Foreign Keys) entre la tabla de empleados de INTEGRADO y los identificadores (EmployeeNo) que envía el biométrico.

---

## 4. Despliegue en el Servidor de Pruebas (192.168.105.17)

Una vez que el código esté asimilado, el despliegue se realizará modificando el archivo `docker-compose.server.yml` del proyecto INTEGRADO. 

### Pasos para Desplegar:
1. Construir la imagen Docker del `cloud_app` en el servidor de Debian.
2. Agregar el siguiente bloque al `docker-compose.server.yml`:

```yaml
  biometricos-cloud:
    build: 
      context: ./path/al/codigo/chismoso/backend
      dockerfile: Dockerfile.cloud
    container_name: albatros_biometricos
    restart: unless-stopped
    ports:
      - "8090:8000" # El puerto que el Edge App ya está esperando
    environment:
      - DATABASE_URL=postgresql://user:pass@albatros-db:5432/integrado_db
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - albatros-db
    networks:
      - albatros_net
```

3. Ejecutar `docker-compose -f docker-compose.server.yml up -d biometricos-cloud` para levantar el contenedor.
4. Redirigir el tráfico del proxy inverso (Nginx/Traefik) si es necesario, o mantener el puerto `8090` abierto exclusivamente para el tráfico de la intranet (oficina).

---

## 5. Siguientes Pasos (Roadmap)

- **Frontend**: Desarrollar las vistas en React/Vue dentro de INTEGRADO para que los administradores consuman los endpoints de `/api/reports/` generados por el `cloud_app`.
- **Sincronización Bidireccional**: Configurar el Cloud App para que envíe comandos al Edge App (ej. Registrar un nuevo usuario en la base de datos de INTEGRADO y que la cara baje al dispositivo Hikvision automáticamente).
