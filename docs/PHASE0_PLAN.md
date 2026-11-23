# Phase 0 Plan and Pre-Build Report

**Date:** 2026-11-24
**Status:** Report for approval. No application code has been written. No Studio endpoint was called, no program was deployed, no keys were generated.
**Scope of this document:** Section 14 of Project Brief v4, items 1-7.

---

## 0. Summary and blockers

The repository is empty. The Solana toolchain is largely present, but three things block a full Phase 0 build on this machine:

1. **No database or cache runtime.** Docker, Docker Compose, PostgreSQL and Redis are not installed, and this account has no passwordless `sudo`. Phase 0 needs PostgreSQL and Redis.
2. **Disk headroom is marginal.** 6.8 GB free on `/` (5.4 GB of it reclaimable from `~/.cache`). Rust/Anchor builds, `node_modules` and container images will need more.
3. **Wallet testing needs a human.** At least one browser wallet must be exercised for the Phase 0 gate. This environment has no browser wallet extension, and the agent cannot reliably install one.

None of the three is an architectural problem. Each needs a decision or an installation by the human (Section 8, Q1-Q2).

The brief's documentation assumptions are also partly stale. Anchor moved to `otter-sec`, the TypeScript package was renamed, `anchor test` now defaults to Surfpool/LiteSVM, and Jupiter's hosts and rate limits changed. The deviations are listed in Section 2. None changes the product plan; several change the exact commands and package names.

---

## 1. Repository and environment

### 1.1 Repository

| Item | Finding |
|---|---|
| `trystsol/` contents | Empty (no files, no hidden files) |
| Git | Not initialised |
| Existing code to preserve | None |

### 1.2 Machine

| Item | Value | Note |
|---|---|---|
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-44 | **Native Linux, not WSL2**; brief assumes Windows + WSL2 |
| CPU / RAM | 8 cores / 14 GiB (7.8 GiB available) | Adequate |
| Disk | 6.8 GB free on `/`; 76 GB free on an NTFS mount | Tight; NTFS is unsuitable for builds |
| Virtualisation | none | No nested VMs |
| Privileges | no passwordless `sudo` | Blocks system package installs |
| Network | Devnet reachable; cluster version `4.5.0-beta.0` | Verified with `solana cluster-version` |

### 1.3 Installed tooling

| Tool | Version | Status |
|---|---|---|
| git | 2.53.0 | OK |
| Node.js | 22.22.1 | OK |
| npm | 9.2.0 | OK |
| pnpm | 12.21.0 | OK |
| Python | 3.14.4 (`venv` OK) | OK |
| Rust / Cargo / rustup | 1.89.0 / 1.89.0 / 1.29.1 | OK (Anchor 1.2 MSRV is 1.89) |
| Solana CLI (Agave) | 4.2.2 | OK, but newer than brief's era |
| `solana-test-validator` | 4.2.2 | OK |
| `cargo-build-sbf` | 4.1.0 | OK |
| Anchor CLI | 1.2.0, at `~/.local/bin/anchor` | Present, **not installed via AVM** |
| AVM | not installed | Needed to pin 1.2.2 per official docs |
| Surfpool | not installed | Anchor 1.x default local validator |
| Docker / Compose | not installed | **Missing** |
| PostgreSQL / Redis | not installed | **Missing** |
| Django / DRF / psycopg | not installed | Expected; will go in a venv |
| `uv` | not installed | Optional |

### 1.4 Missing infrastructure

- PostgreSQL 18.x and Redis 8.x (or Docker equivalents).
- A Python virtual environment with Django, DRF, psycopg, Celery, Redis client.
- AVM-managed Anchor 1.2.2 and a pinned Solana CLI version.
- A funded Devnet deploy wallet (program deployment rent plus test transactions).
- A human-operated browser wallet for the Phase 0 wallet matrix.
- Disk headroom (target: at least 15 GB free on a Linux filesystem).

---

## 2. Documentation read

All pages were read on **2026-11-24**. `https://solana.com/docs/intro/installation` returned HTTP 429, so the Anza CLI documentation was used for the Solana installation instead.

| # | Document | What it establishes | Deviation from the brief |
|---|---|---|---|
| 1 | Anchor — Installation (`anchor-lang.com/docs/installation`) | Rust, Solana CLI, Anchor install; AVM is the recommended path; Windows requires WSL | AVM command is now `cargo install --git https://github.com/otter-sec/anchor avm --force` (repository moved from `coral-xyz`). Quick installer is `solana-install.solana.workers.dev`. Latest documented Anchor is 1.2.2 |
| 2 | Anchor — `Anchor.toml` reference | `[toolchain]` supports `anchor_version`, `solana_version`, `package_manager`; `[scripts]`, `[test]`, IDL output dirs | `[registry]` section removed in 1.0.0. Toolchain pinning works as the brief assumes |
| 3 | Anchor — Emit Events | `emit!` uses program logs and can be truncated; `emit_cpi!` requires the `event-cpi` Cargo feature and `#[event_cpi]` on the accounts struct | CPI events **cannot be subscribed to**; the client must fetch the full transaction and decode the inner instruction. This constrains the indexer design |
| 4 | Anchor — Changelog | 1.2.2 released 2026-10-22; 2.0.0-rc.2 exists; TS package renamed to `@anchor-lang/core`; `anchor test` defaults to Surfpool; LiteSVM is the default test template; CLI no longer shells out to the `solana` binary | Brief's "Anchor 1.2.x stable, 2.0.0 RC" is correct. Package naming and test defaults are stale |
| 5 | Anza — Install the Solana CLI (`docs.anza.xyz/cli/install`) | `sh -c "$(curl -sSfL https://release.anza.xyz/<tag>/install)"`; `agave-install update` | Install domain is `release.anza.xyz`, not `release.solana.com` |
| 6 | SIWS spec (`github.com/phantom/sign-in-with-solana`) | Input/output objects, ABNF message format, `verifySignIn` helper, `connect + signMessage` fallback, domain/nonce/issuance checks | Spec is current, but its example dependency versions are old (wallet-adapter 0.15.34 vs current 0.15.40). `verifySignIn` is JavaScript-only, so Django needs its own verifier |
| 7 | Jupiter — Token API | `GET https://api.jup.ag/tokens/v2/search`; up to 100 mints; returns `isVerified`, `organicScore`, `organicScoreLabel`, `audit` (mint/freeze authority, top-holder %, `isSus`), holder count, liquidity | Hosts changed. Docs describe verified tokens as "Safe to display prominently", which conflicts with our content rules. Jupiter's token audit fields now supply several "on-chain facts" directly |
| 8 | Jupiter — Price API | `GET https://api.jup.ag/price/v3`; up to 50 ids; returns `usdPrice`, `blockId`, `decimals`, `priceChange24h` | Unpriced tokens are **omitted entirely** (no key), not returned as `null` as the brief says |
| 9 | Jupiter — Rate Limits | Keyless 0.5 req/s (30/min); Free 1 req/s (60/min); 60-second sliding window; headers `x-ratelimit-*` | Matches the brief's ~60/min free tier. No `lite-api.jup.ag` host appears in current docs |
| 10 | Jupiter — Studio overview and Create Token | `POST /studio/v1/dbc-pool/create-tx` and `/submit`; presigned image/metadata uploads; parameters incl. `buildCurveByMarketCapParam`, `antiSniping`, `fee.feeBps`, `isLpLocked`, `lockedVestingParam` | Rate limits are now documented (free 100 req/5 min; paid 10 req/10 s). Studio says LP fees are 50% before and after graduation and that **50% of graduated LP may unlock after 1 year** — the brief says LP is permanently locked. No statement about Devnet support was found |
| 11 | Meteora — DBC developer guide and overview | `dynamic_bonding_curve` program ID is the **same on mainnet and Devnet**; DAMM v2 graduation; partner/creator fee splits; mainnet migration keeper, manual migrator supports Devnet | Brief says DBC has "a documented partner fee share" — confirmed. Devnet is explicitly usable, which makes D2 option B testable without Mainnet funds |
| 12 | GitHub — REST rate limits | Unauthenticated 60 req/h; authenticated 5,000 req/h; secondary limits (100 concurrent, 900 points/min, etc.) | Matches the brief |
| 13 | SAS (`attest.solana.com` docs and GitHub) | Credentials → schemas → attestations; expiry; authorized signers; events via self-CPI; program ID `22zoJMtdu4tQc2PzL74ZUT7FrwgB1Udec8DdW4yw4BdG` | Attestations can be **closed to revoke**, which conflicts with "verification history is never deleted". Strengthens the case for keeping SAS out of the source of truth |
| 14 | Package registries (npm, PyPI) | `@anchor-lang/core` 1.2.2 depends on `@solana/web3.js ^1.69.1`; `@solana/wallet-adapter-react` 0.15.40 peers on `web3.js ^1.99.0`; `@coral-xyz/anchor` is legacy at 0.32.1; `@solana/kit` 8.6.0. PyPI: Django 6.1.3 (classifiers list 3.14), DRF 3.18.3, psycopg 3.3.9, PyNaCl 1.6.2, solders 0.29.0 | Confirms the client-library recommendation in Section 4 |

### 2b. Do Phases 0-4 depend on any open decision in Section 15?

**Conclusion: no Phase 0-4 task is blocked by D1-D5, under the defaults. One legal wording issue needs a human confirmation (Q3).**

| Decision | Default | Phase 0-4 impact |
|---|---|---|
| D1 money flow | A: evidence only | None. Nothing in Phases 0-4 holds, releases or custodies money. If B or C were chosen later, escrow/treasury work would be added, not retrofitted into the slice |
| D2 launch provider | Undecided; adapter only | None. The Launch Engine is not created until Gate S. Nothing in Trust or Intelligence imports launch code |
| D3 treasury/monitoring | A: later | None. Phase 4 does scheduled fact refreshes only; no streaming monitors or treasury views |
| D4 countries/payment/legal basis | Devnet, information-only, no payments | Phase 0-4 works under this. See the publication caveat below |
| D5 reviewers | Admin-appointed, conflict declarations | Phase 0 uses one admin-appointed Devnet reviewer. Design accommodates N reviewers |

**Caveat (not a blocker, but it needs a written answer):** Gate S condition 1 includes legal advice "on publishing information about named tokens", yet Phase 4 publishes decision pages about named projects and mints. Proposed default: build Phases 0-4 on Devnet/staging only, label all content as test data, set `noindex`, and obtain the legal review before any public launch in Phase 5. This does not change any code; it changes where the pages are exposed.

---

## 3. Proposed Phase 0 task list and acceptance tests

Phase 0 proves the hard path end to end, thinly. It is not the full application. The order below is dependency-ordered.

### P0-ENV — Environment and toolchain pinning
**Files:** `docs/adr/0005-toolchain-versions.md`, `.env.example`, `docker-compose.yml`, `Makefile` (or `justfile`).
**Work:** install/activate PostgreSQL and Redis (Docker or native); create a Python venv; install AVM and pin Anchor 1.2.2; pin Solana CLI in `Anchor.toml [toolchain]`; record every command and version.
**Acceptance:**
- [ ] `anchor --version` reports the pinned version via AVM.
- [ ] `solana --version` matches `Anchor.toml`.
- [ ] `docker compose up -d postgres redis` (or native equivalent) yields healthy services; `pg_isready` and `redis-cli ping` succeed.
- [ ] Clean checkout builds with documented commands only.

### P0-REPO — Monorepo skeleton and CI
**Files:** `apps/web`, `apps/api`, `apps/indexer`, `programs/project_registry`, `packages/ui`, `docs/`, `DEVELOPMENT_STATUS.md`.
**Work:** create the layout from Section 5, `.gitignore`, formatting/lint config, a CI workflow that runs Django tests, Anchor tests, indexer tests and `pip-audit`/`npm audit`/`cargo audit`.
**Acceptance:**
- [ ] CI runs on a trivial commit and fails correctly on a deliberately broken test.
- [ ] No launch-engine code exists.

### P0-AUTH — SIWS sign-in
**Files:** `apps/api/apps/accounts/`, `docs/adr/0004-wallet-matrix.md`, `apps/web` sign-in flow.
**Work:** server issues a single-use nonce (Redis TTL) plus SIWS input (domain, URI, chainId, statement, issuedAt, expirationTime); verify Ed25519 in Python; validate domain, nonce, expiry, address; issue short-lived access JWT and rotating refresh tokens; rate-limit nonce and verify endpoints; `connect + signMessage` fallback.
**Acceptance:**
- [ ] Valid SIWS message authenticates and creates/returns a user + wallet.
- [ ] Replaying the same nonce fails (single-use enforced atomically, e.g. Redis `GETDEL`).
- [ ] Expired nonce, wrong domain, wrong chainId, tampered message and wrong signature all fail with no user created.
- [ ] Refresh rotation works; reusing a rotated refresh token revokes the family.
- [ ] Rate limit returns 429 above the configured threshold.
- [ ] Unit tests cover ABNF parsing against fixed golden messages; no dependency on a browser.

### P0-DB — Phase 0 schema and services
**Files:** `apps/api/apps/{accounts,projects,milestones,evidence,reviews,chain}/models.py` and migrations.
**Work:** implement the tables in Section 5, the two project status fields, `data_origin`, append-only `Review`/`AuditLog`, and service functions for state transitions with DB check constraints.
**Acceptance:**
- [ ] Migrations apply forward and reverse on an empty database.
- [ ] Illegal transitions are rejected by both service and DB constraint.
- [ ] Update/delete on `Review` and `AuditLog` is not exposed by any code path (test asserts this).
- [ ] Every record that can be simulated carries `data_origin`.

### P0-PROGRAM — Anchor slice
**Files:** `programs/project_registry/programs/project_registry/src/`, `tests/`, `docs/SMART_CONTRACTS.md`.
**Work:** Registry, Reviewer, Project, Milestone, Verification accounts; instructions `initialize_registry`, `add_reviewer`, `register_project`, `create_milestone`, `assign_reviewers`, `submit_milestone`, `verify_milestone`, `reject_milestone`; `emit_cpi!` events; Devnet deploy script.
**Acceptance:**
- [ ] Happy path: initialize → add reviewer → register project → create/submit milestone → assign → verify.
- [ ] PDA derivations match a documented table; wrong program id, wrong owner and fake PDA are rejected.
- [ ] Wrong signer rejected on every privileged instruction.
- [ ] Project authority cannot verify or reject its own milestone.
- [ ] Unassigned or inactive reviewer cannot verify or reject.
- [ ] Double verdict in one round rejected; verifying a non-submitted milestone rejected.
- [ ] Rejection threshold sets `Rejected`; resubmission increments `round` and the previous Verification account still exists.
- [ ] `anchor test` passes with the pinned toolchain.

### P0-CHAIN — Prepare / sign / confirm round trip
**Files:** `apps/api/apps/chain/services.py`, API endpoints, `apps/web` transaction flow.
**Work:** backend prepares metadata hash and instruction payload; client builds and wallet-signs; backend fetches the transaction from RPC, checks program id, instruction, signer, accounts and `meta.err == null`, then records `BlockchainTransaction` (signature, slot, block time) idempotently.
**Acceptance:**
- [ ] A real Devnet transaction round trip succeeds and the signature is verified server-side.
- [ ] A signature from the wrong program or with `meta.err != null` is rejected.
- [ ] Posting the same signature twice creates one record and returns the same result.
- [ ] An unsigned or altered transaction payload is rejected.

### P0-INDEX — Indexer with cursor and backfill
**Files:** `apps/indexer/` (Node 22 worker).
**Work:** poll by program id and signature; fetch full transactions; decode `emit_cpi!` inner instructions; re-read account state; POST normalised facts to a shared-secret Django endpoint keyed on `(signature, instruction_index)`; persist `IndexerCursor` and `ProcessedSignature`.
**Acceptance:**
- [ ] A Devnet verification is written to Postgres with signature, slot and chain status.
- [ ] Restarting the worker does not duplicate rows.
- [ ] Simulated outage: stop worker → send a transaction → restart → transaction is backfilled exactly once.
- [ ] Failed transactions are skipped.
- [ ] A reconciliation command reports DB/chain mismatches.

### P0-WEB — Public project page
**Files:** `apps/web/` project page and components in `packages/ui`.
**Work:** show project, milestone, review outcome, reviewer wallet, evidence URI, source signature and slot, timestamps, `data_origin` badge, “information only, not investment advice” notice. No score, ranking or promotional wording.
**Acceptance:**
- [ ] Verified and rejected outcomes render identically in structure; both show source and time.
- [ ] Loading, empty and error states exist.
- [ ] No rating, “safe/legit”, price view or composite score appears.
- [ ] `data_origin` is visible on every record.

### P0-E2E — End-to-end acceptance
**Acceptance:**
- [ ] On Devnet: sign in → founder registers project → admin approves → project registered on-chain → milestone submitted → assigned reviewer verifies → indexer records → public page shows the verified milestone.
- [ ] Every step produces a signature that the backend confirmed and the page links to.
- [ ] The run is repeatable from a documented script.

### P0-REPORT — Gate report
**Acceptance:**
- [ ] Findings, failures, test commands/dates and updated estimates are in `DEVELOPMENT_STATUS.md` and a gate report in `docs/`.

No time estimate is offered before the slice runs; the brief asks for estimates at the gate.

---

## 4. Recommendations on the Phase 0 ADRs

### ADR-0001 — Indexer: Node 22 worker using the Anchor TypeScript client, posting to Django
**Recommendation:** accept the brief's default.
**Reasons:** the IDL and generated TypeScript types are already needed by the web client; `@anchor-lang/core` decodes accounts and events without hand-written Borsh; one language for chain reads reduces a class of decoding bugs. The worker stays stateless apart from a cursor, and Django remains the only writer to the database.
**Alternatives rejected:** Python + `solders` would need hand-maintained Borsh layouts and has no Anchor event coder; a Rust worker adds a third toolchain to the deploy image for no Phase 0 benefit.
**Consequences:** a third runtime in deployment; the worker needs the IDL versioned alongside the program; the Django write endpoint must authenticate the worker and be idempotent.

### ADR-0002 — Client library: Anchor TypeScript client + `@solana/web3.js` v1 + Wallet Adapter
**Recommendation:** `@anchor-lang/core` 1.2.2, `@solana/web3.js` v1, `@solana/wallet-adapter-react` 0.15.40.
**Evidence:** `@anchor-lang/core` 1.2.2 declares `@solana/web3.js ^1.69.1`; `wallet-adapter-react` 0.15.40 declares peer `@solana/web3.js ^1.99.0`. Both sit on the same major. `@solana/kit` 8.6.0 is not supported by the 1.2.x Anchor TS client; Kit support lands in the 2.0.0 release candidate, which the brief forbids for a security-sensitive program.
**Consequences:** the web app stays on web3.js v1 until Anchor 2.0 is stable and an ADR justifies migration. Phase 0 must record the exact tested versions and the wallet behaviour, not just the metadata.

### ADR-0003 — Attestations: custom program only; SAS deferred
**Recommendation:** custom program is authoritative for project, milestone and verification state. No SAS in Phase 0.
**Reasons:** SAS attestations are closable/revocable, while the brief requires verification history to be permanent; SAS adds credential and schema management plus another program to index; Phase 0 users gain nothing from a second attestation system.
**Revisit if:** third-party apps need to consume TrystSol verdicts without reading our program, or a funder requires a standard credential format. That decision needs its own ADR and a migration plan that keeps the custom program authoritative.

### ADR-0004 — Wallet test matrix
**Recommendation:** test at least Phantom (browser extension) manually, plus automated `connect + signMessage` with generated keypairs. Record Solflare/Backpack, hardware and mobile wallets as **untested** unless the human actually tests them.
**Phase 0 must record:** wallet name, version, `signIn` support, fallback path used, message shown, and result.
**Risk:** the agent cannot install a browser extension; this test depends on the human.

### ADR-0005 — Toolchain pinning
**Recommendation:** AVM-managed Anchor 1.2.2; Solana CLI pinned in `Anchor.toml [toolchain]`; Node 22; Python 3.14 (Django 6.1.x supports it per PyPI classifiers); lockfiles committed. Document the exact install commands and versions.
**Open detail:** the installed Anchor is 1.2.0, while the docs' current stable is 1.2.2 (2026-10-22). 1.2.2 includes macro-hygiene and key-validation fixes, so pin 1.2.2 rather than keep 1.2.0. Devnet currently reports 4.5.0-beta.0 while the local CLI is 4.2.2; the deploy test must confirm compatibility before the gate.

---

## 5. Initial database schema (Phase 0 only)

UUID primary keys unless stated. All tables get `created_at`/`updated_at` where meaningful. Only Phase 0 entities are listed; Roadmap, Dispute, Token, GitHubAccount, Notification and BuilderContribution are deferred to their phases.

### `accounts`

**User** (custom model from day one)
`id` UUID PK · `wallet_primary` FK Wallet (nullable) · `role` enum(`founder`,`reviewer`,`admin`) · `is_active` · `is_staff` · `last_login` · timestamps.

**Wallet**
`id` · `user` FK · `address` char(44) unique · `is_primary` bool · `linked_at` · unique(`user`,`address`).

**SignInChallenge**
`id` · `nonce` char(32) unique · `domain` · `uri` · `chain_id` · `statement` · `issued_at` · `expires_at` · `consumed_at` (nullable) · `wallet_address` (nullable, set after verification) · `request_ip_hash` · timestamps.
Redis holds the authoritative single-use nonce with TTL; this row is the audit trail.

**RefreshToken**
`id` · `user` FK · `token_hash` unique · `family_id` UUID · `parent` FK self (nullable) · `expires_at` · `revoked_at` (nullable) · `replaced_by` FK self (nullable) · `user_agent_hash` · timestamps.

### `projects`

**FounderProfile**
`id` · `user` OneToOne · `display_name` · `bio` · `website` · timestamps.

**ProjectCategory**
`id` · `slug` unique · `name`.

**Project**
`id` UUID · `founder` FK · `name` · `slug` unique · `description` · `website` · `category` FK · `application_status` enum(`Draft`,`Submitted`,`UnderReview`,`Approved`,`Rejected`) · `lifecycle_status` enum(`Active`,`Completed`,`Suspended`) · `data_origin` enum(`simulated`,`devnet`,`mainnet`) · `onchain_project_pda` char(44) nullable · `chain_signature` nullable · `chain_slot` bigint nullable · `chain_lifecycle_status` nullable · `approved_at` · `approved_by` FK User nullable · timestamps.
Constraints: both status enums checked; `data_origin` checked; unique slug; index on `application_status`.

**ProjectApplication**
`id` · `project` FK · `submitted_at` · `reviewed_at` nullable · `reviewer` FK User nullable · `decision` enum(`Pending`,`Approved`,`Rejected`) · `notes` · timestamps.

### `milestones`

**Milestone**
`id` UUID · `project` FK · `title` · `description` · `deadline` date · `status` enum(`Draft`,`Submitted`,`UnderReview`,`Verified`,`Rejected`) · `current_round` int default 0 · `required_approvals` smallint · `onchain_milestone_pda` nullable · `chain_signature` nullable · `chain_slot` nullable · `chain_status` nullable · timestamps.
Constraints: status checked; `current_round >= 0`; `required_approvals >= 1`. **Overdue is derived** (deadline < today and status not Verified/Rejected); never stored.

**MilestoneSubmission** (one per round)
`id` · `milestone` FK · `round` int · `evidence_hash` bytea(32) · `evidence_uri` varchar(128) · `criteria_hash` bytea(32) · `criteria_uri` varchar(128) · `submitted_by` FK User · `submitted_at` · `chain_signature` nullable · `chain_slot` nullable · unique(`milestone`,`round`); `round >= 1`.

### `evidence`

**Evidence**
`id` · `submission` FK · `kind` enum(`repo`,`document`,`url`,`file`) · `uri` · `sha256` bytea(32) · `content_type` · `size_bytes` · timestamps.

### `reviews`

**Reviewer**
`id` · `user` OneToOne · `wallet_address` char(44) · `approved_by` FK User · `approved_at` · `active` bool · `onchain_reviewer_pda` nullable · `chain_signature` nullable · timestamps.

**ReviewerAssignment**
`id` · `milestone` FK · `reviewer` FK · `assigned_by` FK User · `assigned_at` · unique(`milestone`,`reviewer`).

**Review** (append-only; no update/delete code paths)
`id` · `milestone` FK · `submission` FK · `round` int · `reviewer` FK · `decision` enum(`Verify`,`Reject`) · `comment` text · `criteria_hash` bytea(32) · `chain_signature` · `chain_slot` · `created_at`.
Constraints: unique(`milestone`,`round`,`reviewer`); FK to the matching submission round.

### `chain`

**BlockchainTransaction**
`id` · `signature` char(88) unique · `instruction_index` int · `program_id` char(44) · `slot` bigint · `block_time` timestamptz nullable · `status` enum(`confirmed`,`failed`) · `error` text nullable · `processed_at` · `data_origin` check.
Unique(`signature`,`instruction_index`).

**ProcessedSignature**
`signature` char(88) · `instruction_index` int · `slot` bigint · `processed_at`; PK(`signature`,`instruction_index`).

**IndexerCursor**
`id` · `name` unique · `last_signature` nullable · `last_slot` bigint nullable · `updated_at`.

### `audit`

**AuditLog** (append-only)
`id` · `actor` FK User nullable · `action` · `object_type` · `object_id` · `metadata` jsonb · `created_at`.

**Deliberately absent in Phase 0:** Roadmap, Dispute, BuilderContribution, GitHubAccount, Token, Notification, any treasury or analytics table.

---

## 6. Anchor account layout for the Phase 0 slice

The layout below is the Section 7 subset needed for the slice. `emit_cpi!` is used for state-change events; the indexer also re-reads account state, so a lost event cannot lose state.

```rust
// [b"registry"]
pub struct Registry {
    pub admin: Pubkey,
    pub pending_admin: Option<Pubkey>,
    pub reviewer_count: u16,
    pub schema_version: u16,   // proposed addition
    pub bump: u8,
}

// [b"reviewer", registry.key(), wallet.key()]
pub struct Reviewer {
    pub wallet: Pubkey,
    pub active: bool,
    pub added_at: i64,
    pub bump: u8,
}

// [b"project", project_id]  (project_id: [u8;16] UUID)
pub struct Project {
    pub authority: Pubkey,
    pub pending_authority: Option<Pubkey>,
    pub metadata_hash: [u8;32],
    pub metadata_uri: String,       // <= 128
    pub lifecycle_status: u8,       // Active | Completed | Suspended
    pub created_at: i64,
    pub bump: u8,
}

// [b"milestone", project.key(), milestone_id]
pub struct Milestone {
    pub project: Pubkey,
    pub milestone_id: [u8;16],
    pub round: u16,                 // 1-based
    pub evidence_hash: [u8;32],
    pub evidence_uri: String,       // <= 128
    pub criteria_hash: [u8;32],     // proposed addition: fixed at submit
    pub criteria_uri: String,       // proposed addition: <= 128
    pub assigned_reviewers: Vec<Pubkey>, // max 5
    pub required_approvals: u8,
    pub approvals: u8,
    pub rejections: u8,
    pub status: u8,                 // Pending | Submitted | UnderReview | Verified | Rejected
    pub submitted_at: i64,
    pub finalized_at: i64,          // 0 until final
    pub bump: u8,
}

// [b"verification", milestone.key(), round.to_le_bytes(), reviewer.key()]
pub struct Verification {
    pub milestone: Pubkey,
    pub round: u16,
    pub reviewer: Pubkey,
    pub decision: u8,               // 0 = verify, 1 = reject
    pub evidence_hash: [u8;32],
    pub criteria_hash: [u8;32],
    pub timestamp: i64,
    pub bump: u8,
}
```

**Phase 0 instructions:** `initialize_registry`, `add_reviewer`, `register_project`, `create_milestone`, `assign_reviewers`, `submit_milestone`, `verify_milestone`, `reject_milestone`.
**Phase 2 adds:** `transfer_registry_admin`, `deactivate_reviewer`, `update_project_metadata`, `propose_authority_transfer`, `accept_authority_transfer`, `update_project_status`.

### Proposed changes to Section 7 (each needs an ADR; none is applied silently)

1. **Gate `register_project` on the registry admin.** Section 7 seeds the Project PDA by UUID only and does not say who may create it. If registration is permissionless, anyone can squat another team's project id before the founder does. Proposal: `register_project` requires the registry admin as a signer, with the founder as `authority`. This matches the off-chain approval step and preserves the id-only seed.
2. **Fix the review criteria at submit time.** `criteria_hash` currently lives only on Verification, so two reviewers could attest different criteria for the same round. Proposal: store `criteria_hash`/`criteria_uri` on Milestone when `submit_milestone` opens the round; Verification copies them. This makes the published criteria verifiable per round.
3. **Start rounds at 1.** Define `submit_milestone` to increment to 1 on first submission. This avoids a zero-value seed colliding conceptually with “no round” and makes `[b"verification", ..., 0u16]` unambiguously invalid.
4. **Add `schema_version` to Registry (and optionally Project).** Anchor 1.x supports migrations, but an explicit version makes future state changes auditable and lets the indexer reject unknown layouts.
5. **Make `update_project_status` admin-only (Phase 2).** A founder marking their own project `Completed` would be an unverified claim. If founders need to pause, that is a separate instruction with narrower semantics.
6. **Define the rejection threshold formally** in `docs/SMART_CONTRACTS.md`: with `N = assigned_reviewers.len()` and `R = required_approvals`, a milestone is `Rejected` as soon as `rejections >= N - R + 1`; `Verified` when `approvals >= R`; finalisation is idempotent and rejects further verdicts for that round. State that a milestone with no assigned reviewers cannot be finalised.

**Deliberately not proposed:** storing deadlines on-chain (overdue stays derived), storing reviewer identity or evidence content (only hashes and URIs), or adding a score (forbidden by the product rules).

---

## 7. Risks, ambiguities and contradictions

### Blocking or high

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | No `sudo`, Docker, PostgreSQL or Redis on this machine | Phase 0 cannot run the API | Human installs Docker + Compose, or grants sudo, or provides a PaaS database/Redis; see Q1 |
| R2 | 6.8 GB free disk (5.4 GB reclaimable) | Anchor build, node_modules and images may exhaust the disk mid-phase | Free `~/.cache`, set a dedicated `CARGO_TARGET_DIR`, target ≥15 GB free; see Q2 |
| R3 | Only Anchor 1.2.0 installed, not via AVM | Cannot pin reproducibly; misses 1.2.2 fixes | Install AVM and pin 1.2.2 (ADR-0005) |
| R4 | Devnet is 4.5.0-beta.0; local CLI is 4.2.2 | Deploy could fail on toolchain mismatch | Test deploy early with the pinned version; record the result |
| R5 | No browser wallet available to the agent | Phase 0 gate cannot be fully self-verified | Human performs the Phantom test; everything else covered by generated-keypair tests |

### Medium

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R6 | SIWS has no official Python verifier | Hand-written ABNF parsing could accept a malformed message | Implement with golden vectors; test domain/nonce/expiry/address separately; consider a small JS verifier service only if tests show drift (new ADR) |
| R7 | `emit_cpi!` events cannot be subscribed to | Naive indexer misses events | Fetch full transactions and decode inner instructions; re-read account state; cursor + backfill tests |
| R8 | Devnet SOL and program rent | Deploy can be blocked by faucet limits (~5 SOL/request) | Fund early; prefer a small program; document the wallet and top-up procedure |
| R9 | Off-chain/on-chain divergence | DB says Verified while chain does not | Confirm-by-signature before writing; reconciliation job; chain fields prefixed `chain_` |
| R10 | Single reviewer in Phase 0 | One key can finalise a milestone | Design for N reviewers; `required_approvals` is explicit; admin registry and conflict declarations documented |
| R11 | Admin key is a single hot key | Compromise can add reviewers | Devnet-only in Phase 0; multisig required before Mainnet (already in brief) |

### Product/legal and documentation ambiguities

1. **Publication before Gate S.** Gate S covers legal advice on “publishing information about named tokens”, but Phase 4 publishes decision pages. Proposed default: Devnet/staging, labelled test data, `noindex`, until the Phase 5 legal review (Q3).
2. **Jupiter's own wording conflicts with our rules.** Jupiter describes verified tokens as “Safe to display prominently”. We must show `isVerified`/`organicScore` as Jupiter's data with the brief's caveats, never as TrystSol's verdict. This is a content-review checkpoint for Phase 4, not a code blocker.
3. **Studio LP lock.** The brief says LP is permanently locked; the current Studio page says 50% of graduated LP may unlock after one year. Recorded for Gate S/D2, not resolved here.
4. **Studio `feeBps`.** Examples use `feeBps: 100` (1%), but the meaning (total fee, creator share, or protocol share) is still not stated. Open question for Gate S.
5. **Studio Devnet support.** Still undocumented in the pages read. Meteora DBC, by contrast, shares one program ID on Devnet and Mainnet, so D2 option B is testable on Devnet without real funds.
6. **Price API missing tokens.** The brief says “may return null”; current docs say the key is omitted. Phase 4 code must handle absence, not null.
7. **Anchor test story.** The brief implies TypeScript/Mocha Anchor tests; current Anchor defaults to LiteSVM (Rust) and Surfpool. Phase 0 should use Rust LiteSVM tests for state-machine coverage and a thin TypeScript integration test for client/indexer parity. This is a plan adjustment, not a design change.
8. **Environment mismatch.** The brief says the developer machine is Windows with WSL2. The current machine is native Ubuntu without sudo. Either the brief's assumption is out of date, or Phase 0 is being run on a different machine. This needs a human answer before installation work (Q1).

---

## 8. Questions for the human (needed before Phase 0 starts)

| # | Question | Proposed default |
|---|---|---|
| Q1 | Where should the Phase 0 stack run, given no `sudo`, Docker, PostgreSQL or Redis here: (a) install Docker + Compose with your sudo, (b) run on the Windows/WSL2 machine described in the brief, or (c) let me install userspace PostgreSQL/Redis without sudo? | (a) is cleanest and matches `docker-compose.yml` in the brief |
| Q2 | May I free at least 5 GB by clearing `~/.cache` and set a dedicated `CARGO_TARGET_DIR`? Alternatively, can you attach a larger Linux disk? | Yes to both |
| Q3 | Is Devnet/staging-only publication, clearly labelled as test data and `noindex`, acceptable for Phases 0-4 until the Phase 5 legal review? | Yes |
| Q4 | Approve pinning Anchor 1.2.2 via AVM and a Solana CLI version in `Anchor.toml`, even though Anchor 1.2.0 is already installed and Devnet runs 4.5.0-beta.0? | Yes |
| Q5 | Which browser wallet(s) will you test for the Phase 0 wallet matrix, and on which OS/browser? Phantom on Chrome is the minimum. | Phantom; others recorded untested |
| Q6 | Which Devnet wallet should be the program admin and deploy authority, and who funds it? | A fresh Devnet-only keypair, funded by faucet |
| Q7 | Do you approve the six proposed program-design changes in Section 6, in particular admin-gated `register_project` and fixing review criteria at submit? | Yes; each becomes its own ADR |
| Q8 | Confirm D5 default explicitly for Phase 0: you (the human) act as registry admin and appoint the single Devnet reviewer? | Yes |

---

## Approval requested

If this report is approved, Phase 0 starts with P0-ENV and P0-REPO, then proceeds in the order above. I will not start any phase, install system packages, deploy to Devnet, or create wallets until Q1-Q8 are answered.
