# ADR-0012: Helius Devnet RPC for server-side reads

- **Status:** Accepted (Phase 1)
- **Date:** 2026-11-25

## Context

The public Devnet RPC returned HTTP 429 during indexing. Transaction confirmation and
the indexer need a reliable read endpoint. A private RPC URL is a credential.

## Decision

- Use a Helius Devnet endpoint through `SERVER_RPC_URL`.
- The API confirmation path and the indexer prefer `SERVER_RPC_URL`; if absent they
  fall back to `SOLANA_RPC_URL`.
- The browser uses `NEXT_PUBLIC_SOLANA_RPC_URL` (public Devnet). The Helius URL is
  never placed in a `NEXT_PUBLIC_*` variable, never committed, and never logged.
- Validate the endpoint with `getHealth`, `getVersion`, `getSlot` and a real
  `getTransaction` before relying on it. Recorded 2026-11-25: health `ok`, Solana
  core 4.4.1, full Devnet E2E passed over Helius.
- No Helius-specific webhooks or Geyser streaming are used. The indexer still polls
  and re-reads account state; streaming is deferred (D3).

## Consequences

- Rotating the key is a config-only change.
- Free-tier rate limits apply; upgrade or increase the poll interval if 429s return.
- A future migration to QuickNode or another provider only changes
  `SERVER_RPC_URL`.
