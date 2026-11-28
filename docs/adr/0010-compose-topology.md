# ADR-0010: Compose topology for local and staging

- **Status:** Accepted (Phase 1)
- **Date:** 2026-11-25

## Context

Phase 0 ran with a userspace PostgreSQL/Redis fallback because the machine had no
Docker. Docker 29.1.3 and Compose 5.8.0 are now installed. Phase 1 needs one
repeatable stack for API, worker, beat, web, indexer and their services.

## Decision

Use Docker Compose as the standard local/staging topology:

- `postgres` (17) and `redis` (8) with health checks and volumes.
- `migrate` one-shot service: runs migrations and `collectstatic`; the API waits
  for it to complete successfully.
- `api`: Gunicorn, health check on `/api/health/`, static files from a shared
  volume via WhiteNoise.
- `worker` and `beat`: the same API image, Celery worker and beat. The beat schedule
  is the static `CELERY_BEAT_SCHEDULE` in settings; no django-celery-beat table is
  required.
- `web`: Next.js standalone build; public RPC URL and API URL are build arguments
  because `NEXT_PUBLIC_*` is inlined.
- `indexer`: Node worker with `API_URL=http://api:8000`; it uses `SERVER_RPC_URL`
  from `.env` and never exposes it to the browser.
- Named volumes for Postgres, Redis and collected static files.

## Consequences

- `docker compose up --build` is the acceptance command for Phase 1.
- The userspace services remain available as a fallback but are not the standard.
- Host ports 5432/6379 must be free; the fallback uses 5433/6380.
- Compose sets container-host DB/Redis URLs explicitly, overriding the host values
  in `.env`.
- Deployments on a PaaS can reuse the same images and environment contract.
