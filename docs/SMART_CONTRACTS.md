# Smart Contracts — Phase 0 (amended)

Program: `project_registry`
Program ID (Devnet): `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`
Framework: Anchor 1.2.2, Solana CLI 4.1.2, Rust 1.89
Status: **deployed on Devnet** (17 instructions, IDL published). **Unaudited.**

## Accounts (PDAs)

| Account | Seeds | Size (bytes) | Fields |
|---|---|---|---|
| `Registry` | `["registry"]` | 78 | admin, pending_admin, reviewer_count, schema_version, bump |
| `Reviewer` | `["reviewer", registry, wallet]` | 50 | wallet, active, added_at, bump |
| `Project` | `["project", project_id(16)]` | 247 | authority, pending_authority, metadata_hash[32], metadata_uri(≤128), lifecycle_status, created_at, bump |
| `CriteriaTemplate` | `["criteria", template_id(16)]` | 216 | template_id, version, criteria_hash[32], criteria_uri(≤128), published_by, active, created_at, bump |
| `Milestone` | `["milestone", project, milestone_id(16)]` | 589 | project, milestone_id, round u16, evidence_hash[32], evidence_uri(≤128), criteria_hash[32], criteria_uri(≤128), criteria_template_id[16], criteria_version u16, assigned_reviewers[≤5], required_approvals, approvals, rejections, status, submitted_at, finalized_at, bump |
| `Verification` | `["verification", milestone, round_le_u16, reviewer]` | 148 | milestone, round, reviewer, decision, evidence_hash, criteria_hash, timestamp, bump |

`milestone_id` and `template_id` are database UUIDs (16 bytes), so both sides
derive the same PDA. Rounds are 1-based.

## Enums

- `LifecycleStatus`: Active, Completed, Suspended.
- `MilestoneStatus`: Pending, Submitted, UnderReview, Verified, Rejected.
- `Decision`: Verify, Reject.

## Instructions

| Instruction | Signer | Accounts | Rules |
|---|---|---|---|
| `initialize_registry` | admin | admin, registry, system | one per program |
| `propose_registry_admin` | registry admin | admin, registry | stores `pending_admin`; new admin must differ |
| `accept_registry_admin` | pending admin | pending admin, registry | pending admin becomes admin; clears pending |
| `add_reviewer` | registry admin | admin, registry, reviewer, system | admin gate; increments reviewer_count |
| `deactivate_reviewer` | registry admin | admin, registry, reviewer | sets active = false; existing assignments remain until a round is expired |
| `publish_criteria_template` | registry admin | admin, registry, criteria_template, system | immutable, versioned criteria; version ≥ 1; hash non-zero; URI ≤128 |
| `register_project` | registry admin | admin, registry, project, system | admin-gated; creates the project with `authority = admin`, `pending_authority = founder`; founder must accept |
| `update_project_metadata` | project authority | authority, project | authority-only; hash non-zero; URI ≤128 |
| `propose_authority_transfer` | project authority | authority, project | stores a new `pending_authority` |
| `update_project_status` | registry admin | admin, registry, project | admin-only lifecycle (`Active`, `Completed`, `Suspended`) |
| `accept_authority_transfer` | pending authority | project | founder signs from their own wallet; sets `authority = signer`, clears pending |
| `create_milestone` | project authority | authority, project, milestone, criteria_template, system | project Active; template must be active; copies criteria hash/URI/id/version |
| `assign_reviewers` | registry admin | admin, registry, project, milestone, reviewer PDAs | 1-5 unique active reviewers; `1 ≤ R ≤ N`; only Pending/Rejected; no change after a verdict in the current round |
| `submit_milestone` | project authority | authority, project, milestone | Pending/Rejected only; opens round+1; accepts **only** evidence hash/URI; criteria are not arguments |
| `verify_milestone` | assigned reviewer | reviewer signer, registry, reviewer, project, milestone, verification, system | see invariants |
| `reject_milestone` | assigned reviewer | same as verify | same invariants |
| `expire_round` | registry admin | admin, registry, project, milestone | finalises a Submitted/UnderReview round as Rejected; recovery for stuck rounds |

## Invariants

1. **Two-step authority.** The admin registers the project but is only interim
   authority. The founder must call `accept_authority_transfer` from their own
   wallet before creating or submitting milestones. No server-held key signs for
   either party. Later transfers use `propose_authority_transfer` + accept.
1a. **Two-step registry admin.** `propose_registry_admin` records a pending admin;
   only that wallet can `accept_registry_admin`. The old admin loses authority on
   acceptance.
1b. **Lifecycle is admin-only.** Only the registry admin can set `Active`,
   `Completed` or `Suspended`. `Suspended` blocks new milestone creation.
2. **Criteria are admin-published and immutable.** `create_milestone` references
   an active `CriteriaTemplate`; the program copies its hash, URI, id and version
   into the milestone. `submit_milestone` has no criteria arguments, so neither the
   founder nor a reviewer can choose or change criteria. `Verification` copies the
   milestone's criteria hash.
3. **`1 ≤ R ≤ N`.** `assign_reviewers` fails if `R > N`, if `R < 1`, or if the
   reviewer list is empty/duplicated/inactive.
4. **No reassignment after a verdict in a round.** `assign_reviewers` is rejected
   for Submitted, UnderReview and Verified milestones. After a round finalises as
   Rejected, the admin may assign a fresh reviewer set for the next round.
5. **Authority self-review is blocked.** The project authority cannot verify or
   reject its own milestone.
6. **Only active, assigned reviewers vote.** Reviewer PDA must match the signer and
   registry; the reviewer must be active and in the milestone's assigned list.
7. **One verdict per reviewer per round.** The `Verification` PDA is initialised;
   a second verdict fails. Earlier rounds are never deleted.
8. **Final status is written by the program.** `Verified` at `approvals >= R`;
   `Rejected` at `rejections >= N - R + 1` (approval impossible); `UnderReview`
   otherwise.
9. **Stuck rounds can be expired.** The admin may finalise a Submitted/UnderReview
   round as Rejected with `expire_round`. The founder may then submit a new round
   and the admin may assign a new reviewer set. History is preserved.
10. **Rounds increment on submission.** Rejected milestones can be resubmitted;
    `round` increments and earlier Verification accounts remain.
11. **Published verdicts require R ≥ 2.** The program allows `1 ≤ R ≤ N` as
    specified, but the API refuses to assign fewer than two approvals and the public
    payload omits milestones with `R < 2`. `R = 1` is internal/dev only and is never
    published as a TrystSol verdict.
12. **URIs and hashes.** URIs are non-empty and ≤128 bytes; evidence and criteria
    hashes must be non-zero. No personal or private data goes on-chain.

## Events

Phase 0 does not emit events. The indexer re-reads account state, which the brief
permits. Phase 2 should add `emit_cpi!` events for consumers while keeping account
state authoritative.

## Off-chain Phase 3 records

Roadmaps, multi-item evidence, review comments, completion percentage and disputes
are off-chain. The program stores only the first evidence URI/hash, criteria and the
verdict. Completion is verified published milestones divided by published
milestones; disputes never alter the on-chain verdict. See ADR-0014.

## Overdue

Derived in Django from `deadline` and status. Never stored.

## Tests (`cargo test`, 19 passing)

Happy path with criteria and two-step authority; founder must accept before
milestones; criteria cannot be chosen/changed by the founder; `R > N` rejected;
authority self-review blocked; unassigned reviewer blocked; duplicate verdict
blocked; verify before submit blocked; non-admin cannot register/publish/manage
reviewers; rejection/resubmission with rounds preserved; rejection threshold
(3 reviewers, R=2); required approvals; wrong milestone id; fake milestone account;
wrong-owner account; deactivated-reviewer deadlock expired and recovered with a new
reviewer set; no reassignment after a verdict; registry-admin two-step transfer;
project metadata authority; project authority propose/accept; admin-only lifecycle
and suspension blocking new milestones.

## Known limits

- Unaudited. Devnet only.
- The program cannot prove two wallets belong to different people. Independence
  depends on the admin-managed registry and conflict declarations.
- The registry admin and upgrade authority are a single Devnet key. They must move
  to a multisig before Mainnet.
- Authority transfer accepts only the pending authority created at registration;
  a general propose/accept flow is Phase 2.
- No on-chain dispute record yet (Phase 3).
