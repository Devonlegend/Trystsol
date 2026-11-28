# Operations Runbook — Devnet MVP

Devnet only. The program is unaudited. No real-money flows.

## Start / stop

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api worker beat indexer
docker compose down
```

- Web: `http://localhost:3000`
- API: `http://localhost:8000` (`/api/health/`)
- Postgres/Redis: 5432/6379
- Migrations and `collectstatic` run in the one-shot `migrate` service.

Host-only fallback: `./scripts/dev-services.sh start` gives Postgres 5433 and Redis
6380; use the host commands in README.

## Health

```bash
curl -s http://localhost:8000/api/health/
docker compose ps
```

The API health check covers Postgres and Redis. Celery has no HTTP health check; use
`docker compose logs worker beat`.

## Deploy the program

```bash
./scripts/deploy-devnet.sh
```

The script prints versions, wallet, balance and a rent estimate before deploying. It
uploads the IDL by default and verifies all 17 instructions. If it reports
insufficient rent, fund the wallet; do not close/redeploy without approval (that
changes Devnet state).

Localnet dry run:

```bash
solana-test-validator --reset --gossip-port 18000 --dynamic-port-range 18001-18100
ANCHOR_CLUSTER=localnet ANCHOR_RPC_URL=http://127.0.0.1:8899 ./scripts/deploy-devnet.sh
```

The validator gossip port must not collide with the Compose API on 8000.

## End-to-end

```bash
cd apps/indexer
DATABASE_URL=postgres://trystsol:trystsol@127.0.0.1:5432/trystsol \
API_URL=http://localhost:8000 \
npm run e2e:devnet
```

It creates/reuses Devnet test keypairs, signs in, creates a founder profile,
roadmap, milestone, multi-item evidence and two reviewer verdicts, then replays the
indexer and checks the public progress page. Devnet SOL is required for fees/rent.

## Database backup / restore

```bash
docker compose exec -T postgres pg_dump -U trystsol -Fc trystsol > trystsol.dump
docker compose exec -T postgres dropdb -U trystsol --force trystsol
docker compose exec -T postgres createdb -U trystsol -O trystsol trystsol
docker compose exec -T postgres pg_restore -U trystsol -d trystsol < trystsol.dump
docker compose restart api worker beat indexer
```

## Keys and secrets

- `.env` is gitignored; never commit it.
- Rotate `SERVER_RPC_URL` (Helius) by changing the URL and restarting api/indexer.
- Rotate `JUPITER_API_KEY`/`GITHUB_TOKEN` in `.env`; restart api.
- Refresh cookies are httpOnly; access tokens are short-lived and memory-only in the
  browser. Clearing the cookie requires logging out.
- The Devnet deploy/admin key is a single local keypair. It must become a multisig
  before any Mainnet work.

## Audits

```bash
cd apps/api && .venv/bin/pip-audit -r requirements.txt
cd apps/web && npm audit --omit=dev --audit-level=high
cd apps/indexer && npm audit --omit=dev --audit-level=high
cd programs/project_registry && cargo audit --ignore RUSTSEC-2026-0387 --ignore RUSTSEC-2026-0385
```

See ADR-0011 for the audit policy.

## Sensitive-data rules

- Do not put private documents, personal data or secrets in evidence URIs, dispute
  reasons or other public fields.
- Evidence is links + hashes only; binary uploads are not accepted.
- Public pages must keep source, fetch time and caveat on every fact.
