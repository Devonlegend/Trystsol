# ADR-0007: Phase 0 program design changes

- **Status:** **Accepted** (2026-11-25), with amendments
- **Supersedes:** the provisional version of this ADR
- **Date:** 2026-11-25

## Context

Section 7 of the brief defines the PDA layout and rules, and explicitly allows
challenges via ADR but forbids silent reverts. Six gaps were identified while
building the slice. The human accepted items 3, 4, 5 and 6, and amended items 1
and 2.

## Accepted decisions

### 1. Founder consent for project registration (two-step accept)

`register_project` is admin-gated. The admin signs from their own wallet; no
server-held key is used.

To prevent an admin from making a founder the authority without consent, the
on-chain registration is two-step:

1. `register_project` (admin signs) creates the project with
   `authority = admin` and `pending_authority = Some(founder)`.
2. `accept_authority_transfer` (founder signs from their own wallet) sets
   `authority = founder` and clears `pending_authority`.

A founder cannot create or submit milestones until they have accepted. The API
creates the accept intent automatically after the admin's registration confirms.
The admin's role is transitional only. The registry admin, upgrade authority and
any remaining admin powers must move to a multisig before any Mainnet step.

**Rejected alternative:** a single transaction co-signed by admin and founder. It
requires a partially-signed transaction handoff between two wallets, which is more
error-prone in the browser and gives no additional safety over the explicit
two-step accept.

### 2. Criteria are published by the admin, not chosen by the founder

- The admin publishes immutable, versioned `CriteriaTemplate` accounts on-chain
  with `publish_criteria_template`: template id, version, criteria hash, criteria
  URI, publisher, active flag.
- `create_milestone` references an active template and the program copies
  `criteria_hash`, `criteria_uri`, `criteria_template_id` and
  `criteria_version` into the milestone.
- `submit_milestone` accepts **only** evidence hash and URI. It has no criteria
  arguments, so a founder cannot choose or change criteria. The milestone's
  criteria remain fixed for every round.
- `Verification` copies the milestone's criteria hash. Reviewer verdicts therefore
  attest the same criteria that were fixed when the milestone was created.

### 3. Rounds are 1-based

The first submission sets `round = 1`. A zero-round Verification PDA cannot exist.
Resubmissions increment the round and preserve earlier Verification accounts.

### 4. `schema_version` on Registry

The registry carries an explicit schema version so future layout changes are
auditable and the indexer can reject unknown layouts.

### 5. `update_project_status` is admin-only (Phase 2)

A founder cannot mark their own project `Completed`. Lifecycle changes are
reviewed actions. The instruction is deferred to Phase 2 but its authorisation
rule is fixed now.

### 6. Review rules (expanded)

- **Validation:** with `N = assigned_reviewers.len()` and
  `R = required_approvals`, the program requires `1 <= R <= N`. `R > N` fails.
- **No reassignment after a verdict in a round:** `assign_reviewers` is only
  allowed while the milestone is `Pending` or `Rejected`; it is rejected for
  `Submitted`, `UnderReview`, `Verified`. Once any verdict exists, the round's
  assignment cannot change.
- **Stuck rounds:** the admin can call `expire_round`, which finalises a
  `Submitted` or `UnderReview` round as `Rejected`. The founder may then submit a
  new round and the admin may assign a fresh reviewer set. This resolves a round
  deadlocked by a deactivated or unresponsive reviewer without deleting history.
- **Deactivation:** `deactivate_reviewer` lets the admin remove a reviewer. A
  deactivated reviewer cannot submit a verdict. If deactivation makes the current
  round impossible to finalise, `expire_round` is the recovery path.
- **Threshold:** `Verified` when `approvals >= R`; `Rejected` when
  `rejections >= N - R + 1` (approval has become impossible); `UnderReview`
  otherwise.
- **Published verdicts require R >= 2.** The program validates `1 <= R <= N` as
  requested, but the API refuses to assign fewer than two approvals and the public
  payload withholds outcomes for milestones with `R < 2`. `R = 1` exists only for
  internal/dev testing and is never published as a TrystSol verdict.

## Consequences

- The Milestone account grows by the criteria template id and version.
- A new `CriteriaTemplate` account and three new instructions
  (`publish_criteria_template`, `accept_authority_transfer`,
  `deactivate_reviewer`, `expire_round`) exist on Devnet.
- The founder must accept authority before milestone work; the UI surfaces the
  pending accept intent.
- Criteria changes require a new admin-published template version.
- Public pages never show a single-reviewer verdict.
- The program remains unaudited and Devnet-only.
- Tests cover `R > N`, founder-chosen criteria, deactivated-reviewer deadlock and
  post-verdict reassignment.
