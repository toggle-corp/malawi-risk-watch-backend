# Malawi Risk Watch — Backend

Django backend for the Malawi Red Cross Society (MRCS) Disaster Risk Management pipeline. Ingests JBA flood forecasts and ARC parametric rainfall data, and feeds outputs into the IFRC Go platform.

## Requirements

- Docker & Docker Compose

## Getting started

```bash
# Start the dev environment
docker compose up

# Apply migrations
docker compose exec web python manage.py migrate

# Create a superuser
docker compose exec web python manage.py createsuperuser
```

## Management commands

### `sync_geo` — Sync administrative boundaries from IFRC GO

Upserts Malawi admin areas (country, regions, districts) from the IFRC GO API. Safe to re-run.

```bash
# Run the sync
docker compose exec web python manage.py sync_geo

# Preview what would be synced without writing to the database
docker compose exec web python manage.py sync_geo --dry-run
```

## Dummy data

Seeds users, JBA forecasts, ARC observations, trigger events, notification recipients, and logs for local development. Safe to re-run.

```bash
docker compose exec web python manage.py create_dummy_data
```

Created users (password `password123`):

| Email | Role | Admin access |
|---|---|---|
| `admin@example.com` | Admin | Superuser |
| `reviewer@example.com` | Reviewer | Staff |
| `viewer@example.com` | Viewer | — |

## Running tests

```bash
docker compose exec web pytest
```

## Linting

```bash
uv run ruff check .
uv run ruff format .
```
