# ADR-0002: Client library

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

Anchor introduced a Kit-based client in the 2.0.0 release candidate. The stable 1.2.x line still ships a web3.js v1 client. The brief requires a wallet-adapter compatibility check before choosing.

## Evidence (checked 2026-11-24 via npm registry)

| Package | Version | Dependency on web3.js |
|---|---|---|
| `@anchor-lang/core` | 1.2.2 | `^1.69.1` |
| `@solana/wallet-adapter-react` | 0.15.40 | peer `^1.99.0` |
| `@coral-xyz/anchor` | 0.32.1 | legacy package name |
| `@solana/kit` | 8.6.0 | not supported by Anchor 1.2 TS client |

## Options

1. Anchor TS client 1.2.2 + `@solana/web3.js` v1 + Wallet Adapter.
2. `@solana/kit` 8.x with manual instruction encoding.
3. Anchor 2.0.0-rc.2 Kit client.

## Decision

Option 1. The Anchor client and Wallet Adapter share the web3.js v1 major, which removes duplicated connection and transaction plumbing. Anchor 2.0 is a release candidate and the brief forbids it for a security-sensitive program.

## Consequences

- The web app stays on web3.js v1 until a future ADR justifies migration.
- Phase 0 records the exact tested versions and wallet behaviour, not just package metadata.
- Revisit when Anchor 2.0.0 is stable and Wallet Adapter ships a Kit-native path.
