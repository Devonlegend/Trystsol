# ADR-0004: Wallet test matrix

- **Status:** Accepted for Phase 0; matrix incomplete pending human testing
- **Date:** 2026-11-25

## Context

The Phase 0 gate requires signature-verified sign-in to work with at least one browser wallet, and requires recording hardware/mobile behaviour as untested when not tested. The agent's environment has no browser wallet extension.

## Decision

- **Primary manual wallet:** Phantom browser extension, tested by the human on the agreed browser.
- **Automated coverage:** generated Ed25519 keypairs sign SIWS messages and legacy `connect + signMessage` messages in backend tests. This covers verification, replay protection and message binding without a browser.
- **Fallback path:** wallets without the `signIn` feature use `connect + signMessage` with an equivalent SIWS-format message (same domain, nonce, chain id and expiry).
- **Recorded as untested unless actually exercised:** Solflare, Backpack, Ledger/hardware, mobile wallets, and any `signIn` variation not observed.

## Test record fields

Wallet name and version, browser, OS, `signIn` support (yes/no), path used, message shown to the user, result, and the date.

## Consequences

- The Phase 0 gate cannot be fully closed by the agent alone; the human must run the Phantom test.
- Results are stored in `docs/WALLET_MATRIX.md` as they are observed.
