# Phase 1 Report — Foundation

**Date:** 2026-11-25
**Status:** Phase 1 foundation implemented and verified locally. Awaiting approval
for Phase 2.

## Objective

Make the Phase 0 slice repeatable and operable: one Compose stack, queue/scheduler,
production guardrails, CI with dependency audits, and an explicit audit policy.

## Delivered

### Compose stack
- `postgres:17` and `redis:8` with health checks and volumes.
- One-shot `migrate` service: migrations + `collectstatic`; the API waits for it.
- `api`: Gunicorn, health check, WhiteNoise static files from a shared volume.
- `worker` and `beat`: Celery worker and beat using the API image.
- `web`: Next.js standalone image.
- `indexer`: Node worker with `API_URL=http://api:8000` and the server-only Helius
  RPC URL.
- `docker compose up --build` is the standard local/staging command.

### Celery
- `apps.chain.tasks.check_rpc_health` — calls the server RPC.
- `apps.chain.tasks.reconcile_chain_state` — checks that milestones with a chain
  PDA still exist; logs mismatches without mutating records.
- `apps.chain.tasks.prune_expired_intents` — removes long-expired unconsumed
  intents.
- Static beat schedule (5 min / 15 min / daily). No extra beat database is needed.

### Settings hardening
- `DJANGO_ENV=production` fails closed on default/short secrets, empty or wildcard
  `ALLOWED_HOSTS`, empty CORS, http origins, or a localhost SIWS domain.
- Production enables HSTS, SSL redirect, secure cookies and referrer policy.
- WhiteNoise serves collected static files; `STATIC_ROOT` is a Compose volume.
- Dependency versions: Gunicorn 27.0.1, WhiteNoise 6.12.0, packaging 26.4.

### CI and audits
- `.github/workflows/ci.yml` with four jobs:
  - API: Postgres + Redis services, Django checks, migrations, 29 tests, pip-audit.
  - Program: Rust 1.89, Solana CLI 4.1.2, Anchor 1.2.2 via AVM, build, 15 tests,
    cargo audit.
  - Indexer: npm ci, 5 tests, build, npm audit.
  - Web: npm ci, production build, npm audit.
- `npm audit --omit=dev --audit-level=high` is the gate. A `toml@5.0.1` override
  removed both high advisories from Anchor's unused TOML parser.
- `cargo audit` allowlists two dev-only LiteSVM advisories with a written rationale
  in ADR-0011.
- CI YAML and `docker compose config` both parse cleanly. The workflow has **not**
  been run on GitHub from this machine.

## Acceptance results

| Check | Result |
|---|---|
| `docker compose up --build` | All services started; API and web return 200 |
| API health | `{"status":"ok","checks":{"database":true,"redis":true}}` |
| Web | `http://localhost:3000` returns 200 |
| Indexer | Processed on-chain state and advanced its cursor |
| Celery task round trip | `check_rpc_health.delay().get()` returned `ok` |
| Beat | Running with the static schedule |
| Demo data | Existing Devnet project `orbit-tools-devnet-e2e-6` restored into Compose Postgres and visible through the API |
| Backend tests | 29 passed |
| Anchor tests | 15 passed |
| Indexer tests | 5 passed, build ok |
| Web build | production build ok |
| pip-audit | clean |
| npm audit (high gate) | web 0 high / 15 moderate; indexer 0 high / 4 moderate |
| cargo audit | 2 dev-only advisories allowlisted; no runtime advisory |

## Findings fixed during Phase 1

1. **Missing `packaging`** in the API image broke Celery's Redis transport. Pinned
   and rebuilt.
2. **Indexer Dockerfile** omitted `package.json` in the builder stage. Fixed.
3. **Port conflicts** between the host dev server and Compose on 8000/3000. Host
   servers are stopped when Compose runs; the userspace DB remains on 5433/6380.
4. **Anchor `toml` high advisories** removed with an npm override; both high
   findings are gone.
5. **Compose demo data**: the Compose Postgres is separate from the userspace DB.
   The existing dump was restored so the UI shows the verified project.

## Open items

1. Run the CI workflow on GitHub and confirm green.
2. Choose the production/PaaS target and verify `DJANGO_ENV=production` there.
3. Phantom manual wallet test (still pending from Phase 0).
4. Revisit the 15 web / 4 indexer moderate advisories when Wallet Adapter supports
   web3.js v2 or a Kit-native path.
5. Remove the two cargo-audit ignores when a Rust-1.89-compatible LiteSVM release
   includes the fixes.

## Next

Phase 2: full Anchor program (authority propose/accept, lifecycle updates, events,
complete adversarial test suite), IDL publication and Devnet deployment script.
