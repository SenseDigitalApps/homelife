# MedSync API

Este directorio contiene el backend de MedSync con Django + DRF.

## Dependencias (Paso 2)

Se definieron dependencias base en `pyproject.toml` para:
- API Django/DRF
- Auth JWT
- PostgreSQL
- Variables de entorno
- Documentacion OpenAPI
- Seguridad y despliegue base

Dependencias opcionales para tareas async:
- `celery`
- `redis`

## Instalacion

Con `uv`:

```bash
uv sync
```

Para incluir opcionales async:

```bash
uv sync --extra async
```

Para incluir herramientas de calidad:

```bash
uv sync --extra dev
```

## Quality checks

Lint:

```bash
ruff check app
```

Auto-fix lint:

```bash
ruff check --fix app
```

Formato:

```bash
black app
```

Verificar formato sin cambios:

```bash
black --check app
```

## Tests (smoke + seguridad)

Ejecucion local:

```bash
python app/manage.py test core
```

Ejecucion en Docker:

```bash
docker compose exec api python app/manage.py test core
```

## Seguridad minima (Paso 13)

- Usa una `DJANGO_SECRET_KEY` robusta (32+ caracteres).
- En ambientes no locales, configura `DJANGO_DEBUG=false`.
- Mantiene HTTPS estricto cuando `DEBUG=false` (`SECURE_SSL_REDIRECT`, HSTS, cookies seguras).
- Usa expiracion corta de access token JWT y refresh token controlado.
- Los endpoints de dominio deben filtrar siempre por `request.user`.
- Nunca loguees tokens, passwords o datos medicos sensibles.

### Politica de secretos por ambiente

- `dev`: secretos locales en `.env`, nunca versionados.
- `stage`: secretos administrados por CI/CD o secret manager, sin valores hardcoded.
- `prod`: secretos obligatorios en secret manager, rotacion periodica y acceso minimo.
- Para JWT en `prod`, habilitar `JWT_ROTATE_REFRESH_TOKENS=true` y `JWT_BLACKLIST_AFTER_ROTATION=true`.
- Reemplazar inmediatamente cualquier secreto expuesto y regenerar tokens activos.

## Backups y retencion (operativo)

Checklist base recomendado para PostgreSQL:

- Backup automatico diario de la base de datos.
- Retencion minima de 30 dias.
- Cifrado de respaldos en reposo.
- Prueba de restauracion al menos 1 vez por mes.
- Acceso restringido a respaldos solo a personal autorizado.
