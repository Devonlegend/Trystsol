# ADR-0011: CI and dependency-audit policy

- **Status:** Accepted (Phase 1)
- **Date:** 2026-11-25

## Context

Phase 1 requires CI with `pip-audit`, `npm audit` and `cargo audit`. The current
tree has known findings that are not all fixable within the pinned stack.

## Findings (2026-11-25)

- **Python:** clean.
- **Rust:** `crypto-bigint 0.5.5` (RUSTSEC-2026-0387) and `ctutils 0.4.2`
  (RUSTSEC-2026-0385). Both are reachable only through LiteSVM dev-dependencies,
  not the on-chain program runtime.
- **npm web:** 2 highs previously came from `@anchor-lang/core → toml`. Forced
  `toml@5.0.1` via an npm override; the high advisories are gone. 15 moderate
  findings remain via web3.js v1 / Wallet Adapter.
- **npm indexer:** 4 moderate findings via web3.js v1's `uuid`.

## Decision

- CI runs all three audits.
- `npm audit --omit=dev --audit-level=high` is the gate. Moderate findings are
  reported but do not fail the build; they are tracked and revisited when Wallet
  Adapter supports a Kit-native/web3.js v2 path.
- `cargo audit` ignores the two dev-only advisories with explicit flags. The
  on-chain runtime closure remains covered.
- `pip-audit` must stay clean.
- Any new high/critical finding fails CI. A temporary ignore requires an ADR
  amendment with a reachability analysis and an expiry.

## Consequences

- The `toml` override is a transitive major override of a package we never parse
  in the browser; it removes the high advisory without changing our code path.
- Upgrading LiteSVM may remove the Rust advisories; remove the ignores when a
  Rust-1.89-compatible release does.
- Moderate findings are visible in CI logs and must be reviewed before Phase 5.
