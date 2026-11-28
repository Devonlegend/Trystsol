# ADR-0001: Indexer language and approach

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

The indexer must turn on-chain project, milestone and verification state into Postgres read models. Anchor emits events via `emit_cpi!`, but the Anchor documentation (read 2026-11-24) states that CPI events cannot be subscribed to: a client must fetch the full transaction and decode the inner instruction. The backend is Django; the web client is TypeScript.

## Options

1. Node worker using `@anchor-lang/core` 1.2.2 and `@solana/web3.js` v1, posting to Django.
2. Python worker using `solders` and hand-written Borsh decoding.
3. Rust worker using `anchor-client`.

## Decision

Option 1. The worker polls signatures for the program id, fetches each transaction with `getTransaction`, rejects transactions whose `meta.err` is non-null, then **re-reads the affected accounts** with the Anchor client and posts a normalised snapshot to a shared-secret Django endpoint keyed on `(signature, instruction_index)`. It persists `IndexerCursor` and `ProcessedSignature` in Postgres.

Account-state re-reading is used as the primary source of truth; `emit_cpi!` events are still emitted for future consumers but are not required for correctness. This follows the brief's allowance to index from account state or events.

## Consequences

- The IDL must be versioned with the program; the worker imports the generated types.
- A third runtime exists in deployment (Django, worker, indexer).
- The Django write endpoint must authenticate the worker and be idempotent.
- Backfill after an outage is a first-class path, tested by stopping the worker mid-flow.
