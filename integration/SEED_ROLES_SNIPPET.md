# Snippet para PR al monorepo INTEGRADO (seed_roles.py + APP_ROLE_HINTS)

## seed_roles.py

```python
"biometrico": {
    "name": "Control de Biométricos",
    "roles": ["servicios_generales", "gth", "admin"],
},
```

## APP_ROLE_HINTS (admin panel)

```python
"biometrico": {
    "servicios_generales": "Imprime el listado final de comedor (corte ≤ 09:00 e inclusiones ya autorizadas por GTH), sin gestionar excepciones.",
    "gth": "Genera listados de comedor y asistencia; registra/quita permisos de excepción en comedor.",
    "admin": "Acceso total (TI): reportes, permisos GTH y administración/monitoreo de dispositivos biométricos.",
},
```

## nginx (ejemplo)

```nginx
location /api/biometrico/ {
    proxy_pass http://127.0.0.1:8003/api/biometrico/;
    proxy_set_header Authorization $http_authorization;
}
location /biometrico/ {
    proxy_pass http://127.0.0.1:5173/;  # o dist estático
}
```
