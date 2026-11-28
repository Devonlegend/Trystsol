# Development Status — TrystSol

**Last updated:** 2026-11-28
**Current phase:** Phase 0-5 MVP complete on Devnet. Awaiting a human pilot/business decision; Phase 6 remains blocked by Gate S.
**Environment:** Ubuntu 26.04 (native Linux). The Docker Compose stack is the
standard and is currently running (API 8000, web 3000, Postgres 5432, Redis 6379).
The userspace PostgreSQL/Redis fallback remains on 5433/6380 (ADR-0006).
Server-side reads use a Helius Devnet endpoint via `SERVER_RPC_URL` (secret,
.gitignored); the browser stays on the public Devnet RPC.

## Completed phases

- **Phase 0 — Vertical slice.** Built, amended per ADR-0007, and demonstrated on
  Solana Devnet. See `docs/PHASE0_REPORT.md`.
- **Phase 1 — Foundation.** Docker Compose stack, Celery worker/beat, production
  settings guard, CI with audits, and audit triage. See `docs/PHASE1_REPORT.md`.
- **Phase 2 — Full program.** Governance and metadata/status instructions, 19 Anchor
  tests, deployment script, IDL published and Devnet upgrade verified. See
  `docs/PHASE2_REPORT.md`.
- **Phase 3 — Proof-of-Build.** Roadmaps, multi-item evidence, reviewer comments,
  disputes, completion percentage and public progress page. 31 backend tests and a
  Devnet E2E. See `docs/PHASE3_REPORT.md`.
- **Phase 4 — Decision pages and integrations.** Jupiter, Mainnet mint facts, GitHub
  signed-file proof, two-tier decision pages and Builder Passport. 46 backend tests.
  See `docs/PHASE4_REPORT.md`.
- **Phase 5 — Hardening.** httpOnly refresh sessions, memory-only access tokens,
  general throttles, URI validation, security headers, noindex/staging stance, admin
  dispute UI, runbook and final Devnet demonstration. See `docs/PHASE5_REPORT.md`.

## Implemented features

### Trust Engine (Phase 0 slice)
- SIWS wallet sign-in with strict message parsing, Ed25519 verification, single-use
  Redis nonce, rotating refresh tokens, throttling and fallback `signMessage`.
- Two-step project authority: admin registers, founder accepts from their own
  wallet before milestone work.
- Admin-published, versioned criteria templates; criteria are immutable and fixed
  at milestone creation; submission accepts evidence only.
- Review rules: `1 <= R <= N`, no reassignment after a verdict, `expire_round` for
  stuck rounds, `deactivate_reviewer`, `R >= 2` for published verdicts.
- Custom UUID Django user, wallets, founder profile, reviewer registry.
- Project draft → submitted → admin approve/reject; admin-gated on-chain
  registration.
- Milestones with deadlines, on-chain creation, reviewer assignment, evidence
  submission with hashes/URIs, verify/reject, resubmission rounds.
- Append-only Review and AuditLog.
- Anchor program with Registry, Reviewer, Project, CriteriaTemplate, Milestone and
  Verification PDAs; 17 instructions and 19 LiteSVM tests.
- Two-step registry admin transfer, project authority propose/accept, authority-only
  metadata updates, admin-only lifecycle status.
- Deployment script with localnet support, IDL publication verification and IDL sync.
- Signed-intent pattern: server prepares, wallet signs, server confirms on RPC.
- Node indexer: signature polling, account-state re-read, explicit Borsh decoder,
  processed-signature cursor, backfill, idempotent ingest.
- Public project page with two-tier framing, source links, timestamps,
  `data_origin` badges and information-only notices.
- httpOnly refresh cookies; memory-only access tokens; no token persistence.
- General API throttles, http(s)-only evidence/criteria URIs, security headers,
  `noindex`/`robots.txt` disallow and a Devnet staging banner.
- Admin dispute list and resolution UI.
- Full Compose stack: API (Gunicorn), worker, beat, web, indexer, Postgres, Redis,
  one-shot migrations/collectstatic.
- Celery tasks: RPC health, chain-state reconciliation, expired-intent pruning;
  static beat schedule.
- Production settings guard and WhiteNoise static serving.
- GitHub Actions CI for backend, program, indexer and web, with pip/npm/cargo
  audits.
- Founder, admin and reviewer dashboard; project manage page with pending-intent
  recovery.
- Off-chain roadmaps with ordered delivery tracks and milestone grouping.
- Multi-item evidence (`repo`, `document`, `url`, `file`) with SHA-256, content type
  and size; first item anchored on-chain.
- Reviewer comments published with verdicts.
- Public completion percentage (verified published milestones only) with a visible
  basis and no composite score.
- Dispute filing and admin resolution, published next to the verdict.

### Intelligence Engine
- Jupiter Token/Price read-only clients with Redis cache, 429 handling and source/
  time/caveat labels.
- Mainnet mint facts via RPC (supply, decimals, authorities, owner program).
- GitHub signed-file repo-control proof and activity cache.
- Project decision endpoint combining reviewed claims + automated sections.
- Token-only decision page with automated facts and no reviewed claims.
- Builder Passport derived only from verified milestones with R>=2; no score.

### Launch Engine
Not started (Phase 6, blocked by Gate S).

## Outstanding tasks

1. Human pilot/business decision; Phase 6 is blocked by Gate S.
2. Decide whether to keep the Helius free tier or upgrade before a pilot.
3. Manual Phantom wallet test and completed `docs/WALLET_MATRIX.md`.
4. Run the CI workflow on GitHub and confirm green (added locally; not executed
   remotely from this machine).
5. Choose the production/PaaS target and verify the production settings guard there.
6. Expose the Phase 2 governance/metadata/status instructions in the API/UI.
7. Configure `JUPITER_API_KEY`, `GITHUB_TOKEN` and a private Mainnet RPC for
   production.
8. Evidence binary upload pipeline, malware scanning and a live GitHub proof test.
9. Security review before any public pilot; Mainnet/audit/multisig are out of scope
   until explicitly approved.

## Known bugs / limitations

- **No browser test of the UI.** The production build and API payload were verified;
  the browser tool was unavailable. Phantom test is pending.
- **Access token in memory.** An XSS can use it while the tab is open; the refresh
  token is httpOnly. The CSP does not yet define `script-src`.
- **Evidence uploads** are references only; binary upload, type allowlist, malware
  scan and separate-origin downloads remain future work.
- **GitHub live proof** still needs a real committed `.trystsol/proof.json`.
- **Mainnet RPC** falls back to the public endpoint; configure a private endpoint.
- **Evidence/criteria/website links** are http(s)-validated; legacy unsafe links are
  suppressed in public payloads.
- **GitHub proof was tested with mocked GitHub content**, not a live repository
  commit. The human must commit `.trystsol/proof.json` to a repo for a live check.
- **Mainnet RPC** falls back to the public endpoint; configure a private Mainnet RPC
  for production.
- **Jupiter/GitHub keys** are optional; keyless/free limits apply.
- **No streaming, alerts, rankings or discovery feeds.**
- **CI workflow added but not yet run on GitHub.** npm highs are resolved via the
  `toml` override; 15 web and 4 indexer moderate advisories remain via web3.js v1 /
  Wallet Adapter. Rust has two dev-only advisories allowlisted in ADR-0011.
- **Helius free tier** is used for server-side reads; upgrade or tune polling before
  a bursty pilot.
- **Admin/deploy key is a single local keypair**, not a multisig. Devnet only.
- **Phase 2 is deployed on Devnet but unaudited.** Registry/admin transfers and
  lifecycle updates are program-level only; API/UI wiring is Phase 3.
- The program was previously redeployed at a new Devnet ID after the original
  account was closed to reclaim rent for a larger build.
- **Anchor 1.2.2 TS account coder** is not used for indexing because its
  encode/decode layout did not match for these accounts (ADR-0009).

## Test results

| Date | Command | Result |
|---|---|---|
| 2026-11-28 | `cd apps/api && .venv/bin/python manage.py test apps.integrations apps.accounts apps.chain` | **47 passed** |
| 2026-11-28 | `cd programs/project_registry && anchor build && cargo test` | **19 passed** |
| 2026-11-28 | `./scripts/deploy-devnet.sh` | Devnet upgrade succeeded; IDL 17 instructions verified; tx `4tNt5toQVbgoaEBuyea5jvzhCBYd5PQFtGmKjKdSWupxWDZbxF1NRrXhz1qeaLYXzXA3dLLC15P6sdjeCsJSHk6k` |
| 2026-11-28 | `cd apps/indexer && npm run e2e:devnet` | passed after hardening; project `orbit-tools-devnet-e2e-10`, two reviewers, sig `3CBgsTBuX2WCAVQtBfRabs1HMwzM4t4m94oG3MteHjjVbzUeCYBTMjkCjShaiLPqyduPVi95RXTzGqnooVoAgq4v` |
| 2026-11-28 | `GET /api/decision/projects/orbit-tools-devnet-e2e-10/` with JUP mint | Jupiter + Mainnet RPC facts returned with source/time/caveat |
| 2026-11-25 | `cd apps/indexer && npm test` | **5 passed** |
| 2026-11-25 | `cd apps/indexer && npm run build` | passed |
| 2026-11-25 | `cd apps/web && npm run build` | passed (Next 16.4.6) |
| 2026-11-25 | `cd apps/indexer && npm run e2e:devnet` | passed with criteria templates, two-step authority and two reviewers over Helius; project `orbit-tools-devnet-e2e-6`, second verify sig `4twMmRUwc3o5QANUCVFK8P2c7nPKTvRwCkKoMRnFytg4BK5s7QjbWU2NVq6UsWBPF42PE2HAgd6sEbR91ZjJ1ZKe` |
| 2026-11-25 | `curl /api/health/` | database true, redis true |
| 2026-11-25 | `docker run --rm hello-world` / `docker compose version` | Docker 29.1.3, Compose 5.8.0 verified |
| 2026-11-25 | `docker compose up --build` | all services healthy; API/web 200 |
| 2026-11-25 | `docker compose exec api python manage.py shell -c "...check_rpc_health.delay().get(...)"` | Celery task returned `ok` |
| 2026-11-25 | `pip-audit` / `npm audit --audit-level=high` / `cargo audit` | Python clean; npm web 15 moderate/0 high; indexer 4 moderate/0 high; Rust 2 dev-only allowlisted |
| 2026-11-24 | Toolchain inventory and docs review | recorded in `docs/PHASE0_PLAN.md` |

## Devnet deployment

- Program: `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`
- Deploy authority: `~/.config/solana/id.json`
  (`FLJpn8DRQmha59NcNu3Sf42JDqUQ5P9L7NonnsbdNUUZ`)
- E2E project: `orbit-tools-devnet-e2e-10`
- Program is unaudited. Devnet only.

## Architectural decisions

- [ADR-0001](docs/adr/0001-indexer-language.md) — Node indexer, account-state reads.
- [ADR-0002](docs/adr/0002-client-library.md) — Anchor TS 1.2.2 + web3.js v1.
- [ADR-0003](docs/adr/0003-attestations.md) — custom program authoritative; SAS
  deferred.
- [ADR-0004](docs/adr/0004-wallet-matrix.md) — Phantom primary; others untested.
- [ADR-0005](docs/adr/0005-toolchain-versions.md) — pinned versions and commands.
- [ADR-0006](docs/adr/0006-local-dev-services.md) — userspace Postgres/Redis.
- [ADR-0007](docs/adr/0007-program-design-changes.md) — six program changes,
  **Accepted** with human amendments (two-step authority, criteria templates,
  expanded review rules).
- [ADR-0008](docs/adr/0008-siws-python-verifier.md) — Python SIWS verifier.
- [ADR-0009](docs/adr/0009-indexer-account-decoder.md) — explicit Borsh reader.
- [ADR-0010](docs/adr/0010-compose-topology.md) — Compose topology.
- [ADR-0011](docs/adr/0011-ci-audit-policy.md) — CI and audit policy.
- [ADR-0012](docs/adr/0012-helius-rpc.md) — Helius server-side RPC.
- [ADR-0013](docs/adr/0013-governance-transfers.md) — governance transfers and
  admin-only lifecycle.
- [ADR-0014](docs/adr/0014-proof-of-build-records.md) — roadmaps, evidence,
  completion metric and disputes.
- [ADR-0015](docs/adr/0015-decision-pages.md) — automated facts, decision pages and
  Builder Passport.
- [ADR-0016](docs/adr/0016-session-hardening.md) — httpOnly refresh sessions and
  memory-only access tokens.

## Open questions for the human

See `docs/PHASE0_REPORT.md` §Open items. Blocking Phase 1: approval to start,
confirmation of ADR-0007, and the target environment for CI/deployment.

## Notes

- Documentation is current as of 2026-11-25.
- No Mainnet deployment, no audit, no real-money flow, no Launch Engine, no Studio
  call.
