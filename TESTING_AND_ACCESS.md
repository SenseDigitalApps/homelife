# MedSync Backend - Guia de pruebas y accesos

Este documento explica como probar el backend actual, el comportamiento esperado de los endpoints, el manejo comun de errores y las credenciales de acceso para desarrollo.

Estas credenciales son solo para entorno local/desarrollo.

## 1) Credenciales de acceso (dev)

### Superadmin de Django
- URL: `http://localhost:8000/admin/`
- Usuario: `superadmin`
- Email: `superadmin@medsync.local`
- Contrasena: `Admin1234!`

### PostgreSQL (Docker)
- Host: `localhost`
- Puerto: `5432`
- Base de datos: `medsync`
- Usuario: `medsync`
- Contrasena: `medsync_password`

Conexion desde host:

```bash
psql -h localhost -p 5432 -U medsync -d medsync
```

O desde contenedor:

```bash
docker compose exec db psql -U medsync -d medsync
```

## 2) Prerrequisitos

Desde `BACKEND/medsync`:

```bash
docker compose up --build -d
docker compose exec api python app/manage.py migrate
```

Prueba de salud:

```bash
curl http://127.0.0.1:8000/health/
```

Esperado:
- `status = "ok"`
- `db = "ok"`

## 3) Pruebas de endpoints principales

### Endpoints publicos
- `GET /` -> `200`
- `GET /health/` -> `200`
- `GET /api/schema/` -> `200`
- `GET /api/docs/` -> `200`

### Endpoints de autenticacion

#### Registro
- `POST /api/auth/register/`
- Cuerpo:
  - `username`
  - `email`
  - `password`
- Esperado: `201` y `{"detail":"User registered successfully."}`

#### Inicio de sesion (Login)
- `POST /api/auth/login/`
- Esperado: `200` con tokens JWT `access` y `refresh`

#### Refresh
- `POST /api/auth/refresh/`
- Esperado: `200` con nuevo `access`
- Refresh invalido o en blacklist -> `401`

#### Cierre de sesion (Logout / blacklist)
- `POST /api/auth/logout/` (requiere Bearer access token)
- Cuerpo: `{"refresh":"<refresh_token>"}`
- Esperado: `205`
- Despues de logout, usar el mismo refresh debe responder `401` en `/api/auth/refresh/`

### Endpoints protegidos de dominio (requieren Bearer token)

#### Dispositivos (Devices)
- `POST /api/devices/` -> crea dispositivo
- `GET /api/devices/` -> lista dispositivos del usuario autenticado
- Sin token: `401`

#### Mediciones (Measurements)
- `POST /api/measurements/` -> crea medicion
- `GET /api/measurements/?from=&to=&device=&parameter=` -> lista filtrada
- Si el dispositivo no pertenece al usuario autenticado: `400`

#### Reportes (Reports)
- `POST /api/reports/` -> crea reporte
- `GET /api/reports/` -> lista reportes
- Ejemplo de validacion: `date_from > date_to` -> `400`

#### Recomendaciones (Recommendations)
- `GET /api/recommendations/` -> lista recomendaciones del usuario
- Nuevas recomendaciones se generan automaticamente al crear mediciones

#### Catalogo de dispositivos (Device Profiles)
- `GET /api/device-profiles/` -> lista perfiles de dispositivos soportados por el sistema
- Retorna UUIDs BLE, parametros soportados, fabricante y modelo
- Sin token: `401`

#### Mediciones batch
- `POST /api/measurements/batch/` -> crea multiples mediciones de una lectura de dispositivo
- Cuerpo:
  - `device`: ID del dispositivo
  - `measured_at`: timestamp de la lectura
  - `readings`: array de objetos con `parameter_type`, `value`, `unit`
- Esperado: `201` con array de mediciones creadas + recomendaciones generadas automaticamente
- Validacion cruzada: si un `parameter_type` no es compatible con el tipo de dispositivo -> `400`
- Ejemplo: enviar `glucose` desde un oximetro -> `400` con mensaje de parametros soportados

## 4) Manejo de errores esperado

- No autorizado (token ausente/invalido): `401`
- Errores de validacion (cuerpo invalido o regla de negocio): `400`
- Refresh en blacklist tras logout: `401`
- Parametro incompatible con tipo de dispositivo: `400` (validacion cruzada contra DeviceProfile)
- Falla de conectividad de DB en health: `"db": "fail"` (el endpoint sigue respondiendo)

## 5) Validacion de tablas en base de datos

Listar tablas existentes:

```bash
docker compose exec db psql -U medsync -d medsync -c "\dt"
```

Tablas core esperadas:
- `auth_user`
- `devices_device`
- `devices_deviceprofile`
- `measurements_measurement`
- `recommendations_recommendation`
- `reports_report`
- `token_blacklist_outstandingtoken`
- `token_blacklist_blacklistedtoken`

Conteo rapido de registros:

```bash
docker compose exec api python app/manage.py shell -c "from django.contrib.auth import get_user_model; from devices.models import Device; from measurements.models import Measurement; from recommendations.models import Recommendation; from reports.models import Report; User=get_user_model(); print({'users':User.objects.count(),'devices':Device.objects.count(),'measurements':Measurement.objects.count(),'recommendations':Recommendation.objects.count(),'reports':Report.objects.count()})"
```

## 6) Validacion integral realizada

El sistema fue probado extremo a extremo en Docker:

- `GET /health/` -> `200`
- `GET /api/devices/` sin token -> `401`
- Registro -> `201`
- Login -> retorna tokens
- Refresh -> `200`
- Crear device -> `201`
- Crear measurement -> `201`
- Filtrar measurements -> `200`
- Listar recommendations -> retorna recomendaciones creadas
- Crear report (rango valido) -> `201`
- Crear report (rango invalido) -> `400`
- Logout -> `205`
- Refresh con token en blacklist -> `401`
- `GET /api/device-profiles/` -> retorna perfil del oximetro YK-67B1
- Batch de oximetro (spo2, pulse_rate, pi_index, hrv) -> `201`, 4 mediciones + 4 recomendaciones
- Batch con parametro incompatible (glucose en oximetro) -> `400`
- Validacion cruzada individual (glucose en oximetro) -> `400`
- Medicion compatible (spo2 en oximetro) -> `201`

24 tests automatizados pasando (core + recommendations).

Actualmente, todos los comportamientos esperados estan funcionando.


SECRET KEY
3GaqykQTj7h55hjNFjxvvkmpitXfPlEWL7BCIt3cbBU2hRHAI7QZ8jtKL_kjWilLKqU

DB PASSWORD
izVlrHniTPyFEa9di_hrWRTh8zVi6ICI


