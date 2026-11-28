# ADR-0008: SIWS verification in Python

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

The official SIWS reference provides `verifySignIn` in `@solana/wallet-standard-util`, which is JavaScript. The backend is Django/Python. The server must verify the Ed25519 signature **and** bind the message fields (domain, nonce, chain id, issued-at, expiry, address).

## Decision

Implement a strict SIWS message parser and verifier in `apps/api/apps/accounts/siws.py`:

- Parse the ABNF message: domain line, address line, optional statement block, then `Key: value` fields in canonical order.
- Reject duplicate or out-of-order fields, unknown fields, and extra content.
- Compare parsed values against the server-issued challenge (not against client-supplied copies).
- Verify Ed25519 with PyNaCl (`nacl.signing.VerifyKey`).
- Consume the nonce atomically (Redis `GETDEL`) before issuing tokens.
- Enforce domain, chain id, issued-at skew (10 minutes, matching Phantom's published threshold), expiry and address binding.

Golden vectors are generated from a known keypair and committed as tests; a JS-generated vector is added if Phantom's construction differs in practice.

## Consequences

- We own the parser and must test it against malformed input, not just the happy path.
- No Node service is required for authentication.
- If real wallets deviate from the spec, the discrepancy is recorded and handled by a superseding ADR.
