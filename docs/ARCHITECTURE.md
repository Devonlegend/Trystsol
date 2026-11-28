# Architecture — Phase 0

## Engines

| Engine | Present in Phase 0 | Code |
|---|---|---|
| Trust | Yes | `apps/api/apps/{accounts,projects,milestones,evidence,reviews}`, `programs/project_registry`, `apps/indexer` |
| Intelligence | No (Phase 4) | future `apps/api/apps/integrations`, `decision_pages` |
| Launch | No (Phase 6, Gate S) | future `apps/api/apps/launch` behind `LaunchProvider` |

Nothing in Trust imports Launch code. The Launch Engine does not exist yet.

## Request and chain flow

```
Wallet (Phantom)                Next.js                    Django API                 Solana Devnet
      |                            |                            |                          |
      |-- connect ---------------->|                            |                          |
      |-- signIn/signMessage ---->|-- nonce ------------------>|  Redis nonce (TTL)       |
      |                            |-- verify message+sig ----->|  Ed25519 + field checks  |
      |                            |<-- access + refresh -------|                          |
      |                            |                            |                          |
      |                            |-- create project --------->|  application_status      |
      |                            |-- submit application ---->|  Submitted               |
      |                            |-- admin decision -------->|  Approved + SignedIntent |
      |                            |<-- register intent --------|                          |
      |-- founder accepts -------->|-- accept intent ---------->|  chain_authority set     |
      |-- sign tx ---------------->|-- build/send transaction --------------------------->|
      |                            |-- confirm(signature) ----->|  getTransaction (RPC)    |
      |                            |                            |  checks program/signer    |
      |                            |                            |  records chain_* fields   |
      |                            |                            |                          |
      |                            |         Indexer polls signatures, re-reads accounts     |
      |                            |<-- POST /indexer/ingest ---|  ProcessedSignature      |
      |                            |                            |  IndexerCursor           |
```

## Proof-of-Build read model (Phase 3)

- Roadmaps group milestones into public delivery tracks; they are off-chain.
- A submission carries 1-10 evidence items. The first URI/hash is anchored on-chain;
  all items are stored off-chain and published.
- Reviewer comments are part of the append-only Review.
- Completion is verified published milestones divided by published milestones.
  Drafts and `R < 2` milestones are excluded; no weighting or composite score.
- Disputes are off-chain, append-only in their reason, and resolved by an admin; the
  on-chain verdict is never altered.

## Intelligence Engine (Phase 4)

- `apps/integrations`: Jupiter, GitHub and Mainnet mint clients. All server-side,
  read-only, Redis-cached and rate-limit aware.
- `apps/decision_pages`: assembles `reviewed` (Phase 3 payload) and
  `automated_sections`; each fact carries source, source URL, fetch time and caveat.
- `apps/passport`: derives the Builder Passport from verified milestones with at
  least two approvals.
- Project and token decision pages are separate routes; token-only pages state that
  no reviewed claims are attached.
- Jupiter/mint facts are Mainnet; the registry remains Devnet. Failures degrade to
  explicit unavailable facts.

## Trust decisions

- The **server prepares** metadata, PDAs and instruction arguments. It does not
  hold a signing key for user actions. Project registration is two-step: the admin
  registers, the founder accepts authority from their own wallet.
- Admin-published criteria templates are selected by the founder at milestone
  creation; submission carries evidence only.
- The **wallet signs**. The API confirms the transaction by fetching it from RPC
  and checking: success, program id, expected signer, expected PDA.
- The **program is authoritative** for project, milestone, reviewer and
  verification state. Postgres is the workflow and read model.
- The **indexer re-reads account state** after each successful transaction, keyed
  on `(signature, instruction_index)`. Phase 0 does not rely on program logs.
- `chain_*` fields are written only by confirmation or indexing. Workflow fields
  (`application_status`, `status`) are separate.

## Intent pattern

`SignedIntent` rows are server-prepared operations with a 15-minute TTL. They
carry the instruction, args, accounts, expected signer, and internal metadata
needed to update Postgres after confirmation. Pending intents can be recovered
after a page reload via `GET /api/chain/intents/pending/`.

## Indexer

Node 22 worker:

1. Read cursor from `GET /api/chain/indexer/state/`.
2. Fetch signatures for the program (newest first) and stop at the cursor.
3. Process oldest-first; skip failed transactions.
4. Fetch the transaction's account keys and their account data.
5. Decode `Milestone` / `Project` with an explicit Borsh reader (ADR-0009).
6. POST snapshots to Django; the server writes `ProcessedSignature` and advances
   `IndexerCursor` idempotently.

Backfill is tested by stopping/blanking and rerunning; the Devnet E2E does this
for real.

## Deployment

Phase 1 standardises on Docker Compose (ADR-0010):

- `postgres`, `redis`, `migrate` (one-shot), `api` (Gunicorn), `worker`, `beat`,
  `web` (Next standalone) and `indexer`.
- Migrations and `collectstatic` run in the one-shot service; the API waits for it.
- A shared static volume is served by WhiteNoise.
- `SERVER_RPC_URL` (Helius) is server-only; the browser uses the public endpoint.
- The userspace Postgres/Redis fallback (ADR-0006) remains for machines without
  Docker; the standard path is Compose.

A PaaS deployment can reuse the same images and environment contract. The Anchor
toolchain is only needed where the program is built/deployed (WSL2 or CI).
