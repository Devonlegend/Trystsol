# API Specification — Phase 0

Base URL: `http://127.0.0.1:8000`. JSON in/out. Bearer access tokens. Errors use:

```json
{"error": {"code": "string", "message": "human readable", "details": {}}}
```

OpenAPI schema: `GET /api/schema/` (drf-spectacular).

## Authentication

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/nonce/` | public, 20/min/IP | returns SIWS input: domain, uri, version, chainId, statement, nonce, issuedAt, expirationTime |
| POST | `/api/auth/verify/` | public, 20/min/IP | `{message, signature}`; verifies Ed25519 + fields, consumes nonce, returns access/refresh and sets the httpOnly refresh cookie |
| POST | `/api/auth/refresh/` | public, 20/min/IP | rotates and detects reuse; reads the refresh cookie (JSON body still supported for API clients) |
| POST | `/api/auth/logout/` | public | revokes the token family from the cookie or JSON body and clears the cookie |
| GET | `/api/auth/me/` | bearer | user, role, wallets |
| PATCH | `/api/auth/me/` | bearer | display_name |
| POST | `/api/auth/me/role/<user_id>/` | admin | set role |

## Projects

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/projects/` | public | approved projects only, alphabetical, no ranking |
| POST | `/api/projects/` | founder/admin | create draft |
| GET | `/api/projects/<slug>/` | public; owner/admin for unapproved | public payload with milestones, submissions, reviews, notices |
| POST | `/api/projects/<id>/submit/` | founder owner | draft/rejected → submitted |
| POST | `/api/projects/<id>/decision/` | admin | `{decision: approve|reject, notes}`; approval returns a `project.register` intent. After it confirms, the API creates a `project.accept_authority` intent for the founder. |
| GET | `/api/criteria/` | bearer | active, admin-published criteria templates |
| POST | `/api/admin/criteria/` | admin | `{version, criteria_hash, criteria_uri}`; returns a `criteria.publish` intent |
| GET | `/api/admin/projects/` | admin | optional `?status=` |
| GET | `/api/founders/projects/` | bearer | own projects with milestone summaries |
| GET | `/api/projects/<id>/manage/` | owner/admin | includes drafts and chain state |
| GET/PUT | `/api/founders/me/` | bearer | founder profile |

## Milestones

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/projects/<id>/roadmaps/` | founder owner | `{title, description, order}`; off-chain roadmap |
| PATCH | `/api/roadmaps/<id>/` | founder owner | update title/description/order |
| POST | `/api/projects/<id>/milestones/` | founder whose authority was accepted | `{title, description, deadline, required_approvals>=2, criteria_id}`; returns `milestone.create` intent. Criteria come from the admin-published template. |
| POST | `/api/milestones/<id>/assign/` | admin | `{reviewer_ids, required_approvals}` with `2 <= R <= N`; returns `milestone.assign` intent |
| POST | `/api/milestones/<id>/submit/` | founder owner | `{evidence: [{kind, uri, sha256, content_type?, size_bytes?}]}` (1-10 items); the first item is written on-chain; criteria cannot be supplied; returns `milestone.submit` intent |
| POST | `/api/milestones/<id>/expire/` | admin | expires a stuck Submitted/UnderReview round; returns `milestone.expire` intent |
| POST | `/api/reviews/<id>/disputes/` | authenticated | `{reason}` (min 20 chars); one open dispute per user per verdict |
| POST | `/api/disputes/<id>/resolve/` | admin | `{status: upheld|rejected, resolution}` |

## Reviews

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/admin/reviewers/` | admin | registry, including on-chain status |
| POST | `/api/admin/reviewers/` | admin | `{wallet_address}`; user must have signed in; returns `reviewer.add` intent |
| POST | `/api/admin/reviewers/<id>/deactivate/` | admin | returns `reviewer.deactivate` intent |
| POST | `/api/milestones/<id>/review/` | reviewer | `{decision: verify|reject, comment}`; returns `milestone.verdict` intent |
| GET | `/api/reviewer/assignments/` | reviewer | assigned milestones |

## Decision pages and integrations

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/decision/projects/<slug>/` | public | reviewed claims + automated sections; every fact has source, source URL, fetched at and caveat |
| GET | `/api/decision/tokens/<mint>/` | public | automated Jupiter + Mainnet mint facts only; no reviewed claims |
| GET | `/api/passport/<user_id>/` | public | Builder Passport from verified milestones with R>=2; no score |
| PATCH | `/api/projects/<id>/token/` | founder/admin | set/clear the Mainnet token mint |
| POST | `/api/integrations/github/challenge/` | founder/admin | `{project_id, repo_url}`; returns the proof message and `.trystsol/proof.json` instructions |
| POST | `/api/integrations/github/verify/` | founder/admin | `{challenge_id}`; fetches the committed proof file and verifies it |
| GET | `/api/integrations/github/<project_id>/` | founder/admin | linked repo status |

Automated facts are not TrystSol verdicts. Jupiter values are Jupiter's Mainnet
data; no ranking or discovery feed is provided.

## Chain

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/chain/intents/<id>/confirm/` | bearer matching intent signer | `{signature}`; fetches the transaction from RPC, checks success/program/signer/PDA, writes `chain_*`, applies the DB transition |
| GET | `/api/chain/intents/pending/` | bearer | recover un-signed, unexpired intents; optional `object_type`, `object_id` |
| POST | `/api/chain/indexer/ingest/` | `x-indexer-secret` | account snapshots; idempotent on `(signature, instruction_index)`; advances cursor |
| GET | `/api/chain/indexer/state/?name=` | `x-indexer-secret` | cursor |

## Operations

| Method | Path | Auth |
|---|---|---|
| GET | `/api/health/` | public |
| GET | `/api/schema/` | public |

The public project payload includes `progress` (`verified`, `total`, `percentage`,
`basis`), `roadmaps`, milestone `roadmap`, per-submission `evidence` items, and
`disputes` on each review. `percentage` is verified published milestones divided by
published milestones; drafts and `R < 2` milestones are excluded.

## Publication rule

The API requires `required_approvals >= 2` for assignment and public output omits
milestones with `R < 2`. The program itself validates `1 <= R <= N`; `R = 1` is
internal/dev only and is never published as a TrystSol verdict.

## Phase 2 governance instructions

`propose_registry_admin`, `accept_registry_admin`, `update_project_metadata`,
`propose_authority_transfer` and `update_project_status` are implemented and tested
in the Anchor program but are **not yet exposed by the API**. API/UI wiring is
Phase 3 work. The Phase 2 program upgrade is deployed on Devnet.

## Intent payload shape

```json
{
  "id": "uuid",
  "intent": "project.register",
  "object_type": "project",
  "object_id": "uuid",
  "payload": {
    "instruction": "register_project",
    "program_id": "7UUN…",
    "signer": "wallet",
    "account": "pda",
    "args": {"project_id_hex": "…", "metadata_hash_hex": "…", "metadata_uri": "…", "founder": "wallet"},
    "accounts": {"admin": "…", "registry": "…", "project": "…", "system_program": "111…"}
  },
  "expires_at": "ISO-8601"
}
```

The client maps `instruction`/`args`/`accounts` to the Anchor program. The server
never signs.
