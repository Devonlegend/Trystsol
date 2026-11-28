# ADR-0013: Governance transfers and admin-only lifecycle

- **Status:** Accepted (Phase 2)
- **Date:** 2026-11-28

## Context

Phase 2 adds the section 7 governance instructions. The registry admin is a single
key on Devnet, the project authority may change hands, and project lifecycle is a
reviewed claim.

## Decision

1. **Registry admin transfer is two-step.**
   - `propose_registry_admin(new_admin)` — current admin signs; stores
     `pending_admin`.
   - `accept_registry_admin()` — the pending admin signs from their own wallet;
     becomes admin and clears the pending value.
   - The old admin loses authority immediately after acceptance.
2. **Project authority transfer is two-step.**
   - `propose_authority_transfer(new_authority)` — current project authority signs.
   - `accept_authority_transfer()` — the pending authority signs; becomes authority.
   - Project registration also uses this accept step (admin registers, founder
     accepts).
3. **Metadata updates are authority-only.** `update_project_metadata` requires the
   current project authority and enforces hash/URI limits.
4. **Lifecycle status is admin-only.** `update_project_status` requires the registry
   admin. `Suspended` blocks new milestone creation in the program; existing
   milestones remain readable and reviewable.
5. **No events in Phase 2.** The indexer re-reads account state after each
   transaction, which the brief permits. Adding `emit_cpi!` events is a later
   enhancement; account state remains authoritative.

## Consequences

- Both governance transfers require the receiving wallet to consent; an admin or
  founder cannot unilaterally hand over control.
- The registry admin still needs to move to a multisig before Mainnet. This ADR
  does not change that.
- The API does not yet expose the new governance instructions; they are program-
  level and tested in the Anchor suite. API/UI wiring belongs to Phase 3/5.
- A suspended project cannot create new milestones; this is enforced on-chain.
