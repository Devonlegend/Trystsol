# ADR-0006: Local development services without root

- **Status:** Accepted (environment-specific)
- **Date:** 2026-11-25

## Context

The brief assumes Docker Compose. The current machine has no Docker, PostgreSQL or Redis, and no passwordless `sudo`. Phase 0 needs both services. Blocking the phase on a system install was rejected in favour of a reproducible userspace fallback.

## Decision

- Repository still ships `docker-compose.yml` as the standard path.
- For this machine, PostgreSQL 17.12 (conda-forge, via micromamba) and Redis 8.2.3 (built from source) run from `~/.local/share/trystsol` on ports **5433** and **6380**.
- `scripts/dev-services.sh` starts, stops and reports both services; `DATABASE_URL` and `REDIS_URL` in `.env` point at them.
- Nothing in application code depends on the userspace location.

## Consequences

- Local ports differ from the Docker defaults to avoid clashes; `.env.example` documents both.
- `pgdata` and Redis data are outside the repo and never committed.
- CI and production use the Docker Compose path; the fallback is not part of deployment.
