# Phase 2 Report — Full Program

**Date:** 2026-11-28
**Status:** Phase 2 complete. The program is deployed and verified on Devnet.

## Objective

Complete the section 7 Anchor program, publish the IDL and add a Devnet deployment
script with a complete adversarial test suite.

## Delivered

### New instructions
- `propose_registry_admin` / `accept_registry_admin` — two-step registry admin
  transfer. The old admin loses authority on acceptance.
- `update_project_metadata` — project authority only; hash/URI validation.
- `propose_authority_transfer` — current authority proposes a successor.
- `accept_authority_transfer` — pending authority accepts (also used for founder
  consent at registration).
- `update_project_status` — registry admin only; `Suspended` blocks new milestone
  creation.

The full set now contains 17 instructions:

`initialize_registry`, `propose_registry_admin`, `accept_registry_admin`,
`add_reviewer`, `deactivate_reviewer`, `publish_criteria_template`,
`register_project`, `update_project_metadata`, `propose_authority_transfer`,
`accept_authority_transfer`, `update_project_status`, `create_milestone`,
`assign_reviewers`, `submit_milestone`, `verify_milestone`, `reject_milestone`,
`expire_round`.

### Tests — 19 passing

Added coverage for:

- two-step registry admin transfer (old admin locked out after acceptance);
- project metadata authority and wrong-signer rejection;
- project authority propose/accept and old-authority lockout;
- admin-only lifecycle status; suspension blocks new milestones;
- wrong-owner account rejection;
- all previous invariants (criteria, `R > N`, no reassignment, deadlock recovery,
  double verdicts, resubmission rounds, thresholds, self-review, fake PDAs).

### Deployment script

`scripts/deploy-devnet.sh`:

1. Prints Anchor/Solana versions, cluster, program ID, wallet and balance.
2. Runs `anchor build`.
3. Runs `anchor program deploy --provider.cluster <cluster>` (IDL uploaded by
   default).
4. Verifies the published IDL contains all 17 instructions.
5. Syncs the IDL artifact into the web app.
6. Prints the on-chain program account.

Localnet override is supported (`ANCHOR_CLUSTER=localnet`,
`ANCHOR_RPC_URL=http://127.0.0.1:8899`). On localnet Anchor skips on-chain IDL
publishing, so the script verifies the generated IDL artifact instead.

## Localnet verification

The script was run against a local validator on isolated ports (gossip 18000 to
avoid the Compose API on 8000):

- Program ID: `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`
- Upgrade signature: `3NNNWF5RyAZ7cwHKYG9dtdYm3TH7kvoMuKMyA7268n369RXwoxBq7njqcbiNy4NXgA3GT8qvDuaFi7ZgoTgb6N2H`
- Program data length: 316,592 bytes
- IDL: 17 instructions verified
- Program account authority: the Devnet deploy key

## Devnet deployment

The deploy wallet was funded and the upgrade completed:

- Upgrade signature: `4tNt5toQVbgoaEBuyea5jvzhCBYd5PQFtGmKjKdSWupxWDZbxF1NRrXhz1qeaLYXzXA3dLLC15P6sdjeCsJSHk6k`
- Deployed slot: `527203785`
- Program data length: 316,592 bytes
- Published IDL: 17 instructions verified
- Program ID: `CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB`
- Remaining balance after deployment: ~1.61 SOL

## Devnet end-to-end after upgrade

Project `orbit-tools-devnet-e2e-8` passed with:

- admin-published criteria
- two-step founder authority
- two reviewers, `R = 2`
- `verified` on-chain and in the public payload
- first verification `5Mf1JyEWP8JiH8U9PbgacAGECD6br5KQ53VCzChMe8bqGCtAJMEGWs2G2e3fqfCrCMnc9wLrHBPw2WNH1uuMuFAi`
- second verification `5VfofaaNh1gZ5mYohQ7TjHR7wp8SQpyaecdWK8JkthbhK8iHLwN3wj3cXm5849SxMEfsFRtVrAXR1KgY3tEqzNQN`
- indexer cursor at slot `527208111`

## Status of artifacts

- `programs/project_registry/target/idl/project_registry.json` — current, 17
  instructions.
- `apps/web/lib/idl/project_registry.json` — synced.
- On-chain Devnet IDL — upgraded and verified, 17 instructions.
- Devnet DB/UI — points to the upgraded program; existing Phase 1/2 records remain
  valid because the program ID did not change.

## Next

Phase 3: expose governance/metadata/status actions in the API and UI, then build
roadmaps, evidence, review flow, disputes and public progress pages. The program is
still unaudited and Devnet-only.
