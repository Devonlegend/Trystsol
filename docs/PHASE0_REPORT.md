# Phase 0 Gate Report

**Date:** 2026-11-25 (amended after the human's review of ADR-0007)
**Status:** Phase 0 slice built, amended, and demonstrated on Solana Devnet.
Awaiting approval to start Phase 1 implementation.

## Gate checklist

| Requirement | Result | Evidence |
|---|---|---|
| Signature-verified sign-in with nonce replay protection | **Pass** | 18 backend auth tests; three wallets signed in over HTTP in the Devnet E2E |
| Real Devnet round trip: client builds, wallet signs, backend verifies, indexer records | **Pass** | Project `orbit-tools-devnet-e2e-6` over Helius; second verification signature `4twMmRUwc3o5QANUCVFK8P2c7nPKTvRwCkKoMRnFytg4BK5s7QjbWU2NVq6UsWBPF42PE2HAgd6sEbR91ZjJ1ZKe` |
| Indexing from account state with cursor and backfill after outage | **Pass** | E2E blanks `chain_*`; a fresh cursor replays 7 transactions and restores `chain_status=verified`; indexer tests cover cursor, failures and ordering |
| Automated tests | **Pass** | 25 Django tests, 15 Anchor/LiteSVM tests, 5 indexer tests, web production build |
| Findings and updated estimates | **This document** | — |

## Accepted amendments

ADR-0007 is **Accepted**:

1. **Two-step founder consent.** `register_project` (admin) creates the project
   with `authority = admin`, `pending_authority = founder`. The founder signs
   `accept_authority_transfer` from their own wallet before milestone work.
2. **Admin-published criteria templates.** Immutable, versioned
   `CriteriaTemplate` accounts. `create_milestone` copies the selected template;
   `submit_milestone` accepts only evidence and cannot change criteria.
3. Rounds are 1-based.
4. `schema_version` on Registry.
5. `update_project_status` is admin-only (Phase 2).
6. Review rules: `1 <= R <= N`; no reassignment after a verdict in a round;
   `expire_round` for stuck rounds; `deactivate_reviewer`; `R >= 2` for published
   verdicts; rejection threshold `N - R + 1`.

## What runs on Devnet

- Program: `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`
- Deploy authority: `~/.config/solana/id.json`
  (`FLJpn8DRQmha59NcNu3Sf42JDqUQ5P9L7NonnsbdNUUZ`)
- Registry initialised.
- E2E over Helius (project `orbit-tools-devnet-e2e-6`): criteria template
  published, project registered by the admin, founder accepted authority,
  milestone created from the template, two reviewers assigned, evidence submitted,
  both reviewers verified. Verification signatures:
  `5Mjo8sTDRACeRLaJ75asM7Wh3uLRa2mC3q3Mwt8VYnZR3yHVj3oYXCbaEjQ8ae4L1jV4CZWsBnEioVaz9zGokJBp`
  and `4twMmRUwc3o5QANUCVFK8P2c7nPKTvRwCkKoMRnFytg4BK5s7QjbWU2NVq6UsWBPF42PE2HAgd6sEbR91ZjJ1ZKe`.
- Public API payload shows the verified milestone, two independent reviews, the
  admin-published criteria hash and the transaction source.

## Test results (commands run 2026-11-25)

| Area | Command | Result |
|---|---|---|
| Backend | `cd apps/api && .venv/bin/python manage.py test apps.accounts apps.chain` | 25 passed |
| Program | `cd programs/project_registry && anchor build && cargo test` | 15 passed |
| Indexer | `cd apps/indexer && npm test` | 5 passed |
| Indexer build | `npm run build` | passed |
| Web build | `cd apps/web && npm run build` | passed (Next 16.4.6, Turbopack) |
| Devnet E2E | `cd apps/indexer && npm run e2e:devnet` | passed with two reviewers and the amended rules |

## Findings

1. **Anchor 1.2.2 TypeScript account coder is unreliable for this IDL.** Encoding
   a `Milestone` produced 140 bytes while decoding expected 157; padded buffers
   decoded incorrectly. Replaced with an explicit Borsh reader (ADR-0009), updated
   for the new criteria fields and exercised on real Devnet accounts.
2. **Reviewer PDA bug caught by Devnet.** The server used the program id instead of
   the registry PDA for the reviewer seed. Fixed and verified on-chain.
3. **Unassigned milestones have `required_approvals = 0`.** A valid state; the
   decoder no longer rejects it.
4. **Public Devnet RPC returned 429s** during early indexing. A Helius Devnet
   endpoint is now configured as `SERVER_RPC_URL`; the API confirmation and indexer
   use it, and the full E2E passed over Helius. The browser stays on the public
   endpoint.
5. **Next.js + Anchor browser bundle needs Node stubs.** `fs`/`path`/`os` are
   aliased to a stub; build passes. The npm audit still flags a high advisory in
   Anchor's unused TOML parser; triage is a Phase 1 item.
6. **Program redeploy.** The original Devnet program account was closed to reclaim
   rent for the larger amended build, then redeployed at
   `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`. This is Devnet test state only.
7. **The wallet matrix is incomplete.** No browser was available to the agent.
   Phantom must be tested manually.
8. **Audits.** Python clean. Rust has two advisories in the dev-only LiteSVM graph.
   npm has two highs via Anchor's unused TOML parser and moderates via web3.js v1 /
   Wallet Adapter. Triage is Phase 1 CI work.

## Updated estimates

Judgment, not measurement. Single developer with a coding agent, Devnet only.

| Phase | Estimate | Main uncertainty |
|---|---|---|
| Phase 1 — Foundation | 1.5-2.5 weeks | CI, Docker/Compose on the target host, deployment plumbing |
| Phase 2 — Program | 2-3 weeks | Authority propose/accept, status updates, events, more adversarial tests |
| Phase 3 — Proof-of-Build | 3-4 weeks | Roadmaps, dispute records, evidence storage/scanning, E2E |
| Phase 4 — Decision pages + integrations | 2-3 weeks | GitHub proof, Jupiter caching/rate limits, content rules review |
| Phase 5 — Hardening | 1.5-2.5 weeks | Session hardening, security review, accessibility, docs |
| **Phase 1-5 total** | **10-15 weeks** | Consistent with the study's 11-15 weeks for Phases 0-4; Phase 0 is done |

Excludes legal review, third-party audit and Mainnet work.

## Open items for the human

1. **Approve Phase 1 implementation** (foundation: CI, Docker/Compose, audits).
2. **Docker daemon** is installed and verified (29.1.3, Compose 5.8.0). Phase 1
   can build the full Compose stack.
3. **Wallet test:** run Phantom and record `docs/WALLET_MATRIX.md`.
4. **Publication:** Devnet/staging-only and `noindex` until legal review — recorded
   as your decision.
5. **RPC:** Helius Devnet is configured for server-side reads; decide whether to
   keep the free tier or upgrade before a pilot.
6. **Key:** keep the current Devnet deploy/admin key for Phase 1; multisig before
   Mainnet.

## Known limitations

- Tokens are stored in `localStorage`; move to an httpOnly/BFF session before
  public launch.
- No evidence upload pipeline; only links and hashes.
- Reviewer comments are supported by the API but not exposed in the reviewer
  dashboard.
- Dispute path is a placeholder until Phase 3.
- No CI workflow yet; Phase 1 adds CI with dependency audits.
- The public page is client-rendered; verified through its API payload and
  production build, not through a browser in this environment.
- The program is unaudited and the admin is a single Devnet key.
