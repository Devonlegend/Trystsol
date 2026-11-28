# ADR-0017: D1-D5 product decisions

- **Status:** Accepted (human decisions, 2026-11-28)
- **Date:** 2026-11-28

## Context

The brief left D1-D5 to the human. The agent must not decide them and must build
only under the defaults until answered. The human answered after Phase 5.

## Decisions

1. **D1 — Evidence only.** TrystSol never holds, releases or custodies money. No
   escrow or community-treasury program is built. This keeps the MVP out of custody
   and money-transmission scope.
2. **D2 — Jupiter Studio API is the preferred launch provider**, but Phase 6 remains
   blocked by Gate S. No Studio code, calls, tables or provider-specific terms are
   added before the gate. The adapter boundary is the only commitment now.
3. **D3 — Basic treasury view.** A project may declare a wallet; the public page shows
   its SOL balance and recent transaction signatures with chain, source, fetch time
   and a caveat that ownership is not proven. No custody, token valuation, streaming
   monitors or alerts.
4. **D4 — Devnet, information-only, no payments.** Legal advice and a written
   decision are required before any public/payment/Mainnet step.
5. **D5 — Admin-appointed reviewers**, with conflict declarations. External reviewer
   nomination can be revisited for a pilot.

## Consequences

- The MVP scope remains evidence, decision pages and a read-only treasury view.
- D2 preference does not authorise Phase 6; Gate S still requires legal advice,
  Jupiter answers and a pilot/business decision.
- Treasury reads are labelled as declared, not ownership-proven; message signing
  cannot prove control of a multisig vault.
- No mainnet deployment, audit, payments or token sales follow from this ADR.
