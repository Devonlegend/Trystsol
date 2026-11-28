# Product Decisions (D1-D5)

**Date:** 2026-11-28
**Status:** Recorded. D2 remains blocked by Gate S.

| # | Decision | Answer | Effect |
|---|---|---|---|
| D1 | Money flow | **A. Evidence only** | TrystSol shows proof and verdicts; it never holds, releases or custodies money. No escrow/treasury architecture. |
| D2 | Launch provider | **A. Jupiter Studio API** (preferred, not implemented) | No Phase 6 work until Gate S. The adapter boundary remains; no Studio calls or schema. |
| D3 | Treasury/monitoring | **B. Basic treasury view** | A declared project wallet can show SOL balance and recent transactions, with source/time/caveat. No custody, valuation, streaming or alerts. |
| D4 | Legal/payment basis | **Keep Devnet, information-only, no payments** | No token sales, fundraising, payments or Mainnet until legal advice and an explicit decision. |
| D5 | Reviewers | **Admin-appointed** | Admin appoints reviewers with conflict declarations on file. External nomination can be revisited for a pilot. |

## Still required before Phase 6 / Gate S

1. Written legal advice on token launches and publishing information about named
   tokens; recorded decision to lift the no-token-sales rule.
2. Jupiter confirmation of API key access, Devnet support and integrator earnings.
3. A passed Phase 3 pilot and business decision gate.

Selecting Jupiter Studio as the preferred provider does **not** satisfy any Gate S
condition and does not authorise implementation.
