# Wallet Test Matrix — Phase 0

Last updated: 2026-11-25.

| Wallet | Environment | `signIn` | Path tested | Result | Date |
|---|---|---|---|---|---|
| Phantom (browser extension) | Chrome/desktop | unknown in this environment | SIWS `signIn`, with `signMessage` fallback implemented | **Untested by a human** | — |
| Solflare | — | — | — | **Untested** | — |
| Backpack | — | — | — | **Untested** | — |
| Ledger / hardware | — | — | — | **Untested** | — |
| Mobile wallets | — | — | — | **Untested** | — |

## Automated coverage (not a substitute for a wallet test)

`apps/api/apps/accounts/tests/` uses generated Ed25519 keypairs to cover:

- SIWS message construction and parsing, with and without a statement.
- Signature verification and rejection of a signature from another key.
- Domain, nonce, chain id, issued-at and expiry binding.
- Single-use nonce and replay rejection.
- Refresh-token rotation and reuse detection.
- A real Devnet end-to-end run signs SIWS messages with three keypairs
  (`apps/indexer/scripts/e2e-devnet.ts`).

These prove the server side. They do not prove how Phantom constructs the message,
what it displays, or that its `signIn` output matches the spec.

## Required manual test

1. Start the API and web app, open `/login`, connect Phantom on Devnet.
2. Click **Sign in with Solana**.
3. Record:
   - Phantom version and browser/OS.
   - Whether `signIn` was used or the `signMessage` fallback.
   - The message Phantom displayed (domain, statement, nonce, expiry).
   - Result, and any console error.
4. Add the row to the table above.

Record hardware and mobile results as **untested** unless actually exercised.
