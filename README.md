# TrystSol

Proof-of-build for projects launching on Solana. Wallet sign-in, independent
milestone review, on-chain records on Devnet, and a public page that shows each
claim with its source and timestamp.

**Status:** Phase 0 vertical slice complete and demonstrated on Devnet. Awaiting
human approval to start Phase 1. See `docs/PHASE0_REPORT.md` and
`DEVELOPMENT_STATUS.md`.

Information only. Not investment advice. No scores, rankings or safety ratings.

## Repository layout

```
apps/web/                     Next.js 16, React 19, Wallet Adapter, Anchor client
apps/api/                     Django 6.1, DRF, Postgres, Redis, Celery
apps/indexer/                 Node 22 worker, explicit Borsh reader, cursor + backfill
programs/project_registry/    Anchor 1.2.2 program and LiteSVM tests
packages/ui/                  Reserved for shared UI (Phase 5)
docs/                         Architecture, schema, API, security, ADRs, reports
scripts/dev-services.sh       Userspace Postgres + Redis fallback (no sudo)
```

## Local setup

Versions are pinned in `docs/adr/0005-toolchain-versions.md` and lockfiles.
The short version: Node 22, Python 3.14, Rust 1.89, Solana CLI 4.1.2, Anchor
1.2.2, PostgreSQL 17, Redis 8.

### Standard path: Docker Compose

```bash
cp .env.example .env
# set SERVER_RPC_URL to a private Devnet RPC (Helius/QuickNode) if you have one
docker compose up --build
```

- Web: `http://localhost:3000`
- API: `http://localhost:8000` (health at `/api/health/`)
- Postgres: `localhost:5432`, Redis: `localhost:6379`
- Migrations and `collectstatic` run once in the `migrate` service.
- API, Celery worker, beat, web and indexer run as separate services.

The browser uses `NEXT_PUBLIC_SOLANA_RPC_URL` (public Devnet). The API and indexer
use `SERVER_RPC_URL` (private credential, never exposed to the browser).

### Host-only fallback (no Docker)

```bash
./scripts/dev-services.sh start      # PostgreSQL 5433, Redis 6380
cp .env.example .env                 # keep DATABASE_URL 5433 and REDIS_URL 6380
```

Then run the API, web and indexer from their directories:

```bash
cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate && .venv/bin/python manage.py runserver 127.0.0.1:8000

cd apps/web && npm install && cp .env.example .env.local && npm run dev
cd apps/indexer && npm install && cp .env.example .env && npm run dev
```

### Production settings

Set `DJANGO_ENV=production`. The API refuses to start with a default/short secret,
empty or wildcard `ALLOWED_HOSTS`, empty CORS, http origins, or a localhost SIWS
domain. It enables HSTS and secure cookies. See `docs/SECURITY.md`.

## Decision pages

- `/projects/<slug>` shows reviewed claims plus automated facts.
- `/tokens/<mint>` shows automated Jupiter and Mainnet mint facts only.
- `/builders/<user-id>` shows the Builder Passport (verified milestones only, no score).

Configure `JUPITER_API_KEY`, `GITHUB_TOKEN` and `MAINNET_RPC_URL` for production
limits and reliability. Keys are server-side only.

## Program

```bash
cd programs/project_registry
anchor build
cargo test                 # 19 LiteSVM tests
```

Deploy and publish the IDL:

```bash
./scripts/deploy-devnet.sh
# Local validation without Devnet funds:
ANCHOR_CLUSTER=localnet ANCHOR_RPC_URL=http://127.0.0.1:8899 ./scripts/deploy-devnet.sh
```

Program ID: `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`.

**Deployment status:** the Phase 2 build (17 instructions) is deployed on Devnet;
the on-chain IDL was verified after the upgrade. It remains unaudited and Devnet-only.

## Tests

```bash
cd apps/api && .venv/bin/python manage.py test apps.accounts apps.chain
cd programs/project_registry && cargo test
cd apps/indexer && npm test && npm run build
cd apps/web && npm run build
```

## Devnet end-to-end

Requires the API running, a funded `~/.config/solana/id.json`, and the program
deployed. It creates/reuses founder and reviewer keypairs, signs in with SIWS,
runs the full flow with real transactions, blanks the indexer-owned fields, then
replays the indexer to prove backfill.

```bash
cd apps/indexer
npm run e2e:devnet
```

Latest successful run: project `orbit-tools-devnet-e2e-10`, second verification
signature `3CBgsTBuX2WCAVQtBfRabs1HMwzM4t4m94oG3MteHjjVbzUeCYBTMjkCjShaiLPqyduPVi95RXTzGqnooVoAgq4v`.
It covers the hardened stack, founder profile, roadmap, multi-item evidence, two
independent reviewers, the Phase 2 program, and Helius for server-side reads.

## Security

Read `docs/SECURITY.md` and `docs/RUNBOOK.md` before exposing anything publicly.
Devnet only. No real-money flows. Refresh tokens are in an httpOnly cookie; access
tokens are memory-only. Never commit `.env` or keypairs.
