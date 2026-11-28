# ADR-0009: Explicit account decoder in the indexer

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

The indexer must decode `Milestone` and `Project` accounts from Devnet. `@anchor-lang/core` 1.2.2's `BorshAccountsCoder` was tried first. With the generated IDL it produced inconsistent results: encoding a fully populated `Milestone` yielded 140 bytes while decoding expected 157, and decoding a padded buffer returned the wrong enum and zeroed counters. A real Devnet account also exposed a separate bug in our own first decoder (rejecting `required_approvals = 0`, which is valid before assignment).

## Decision

Use a small explicit Borsh reader in `apps/indexer/src/decode.ts`:

- Verify the Anchor account discriminator (`sha256("account:Milestone")[0..8]`).
- Read fields in the exact order of `programs/project_registry/src/state.rs`.
- Treat `required_approvals = 0` as valid for an unassigned milestone.
- Reject unknown status indexes and truncated buffers, which are logged and skipped.
- Cover the reader with tests that encode known snapshots, including trailing account padding.

The browser client still uses `@anchor-lang/core` to build instructions; this ADR only concerns reading account state.

## Consequences

- The decoding layout is duplicated in Rust and TypeScript. A field change requires updating both and the fixture tests.
- No dependency on a coder whose encode/decode behaviour did not match for these accounts.
- Real Devnet data exercised the reader in the Phase 0 end-to-end run; the unassigned-milestone case is now covered.
- Revisit if `@anchor-lang/core` fixes its account coder and a test proves parity.
