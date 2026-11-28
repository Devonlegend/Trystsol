# Database Schema — Phase 0

Postgres 17. UUID primary keys unless stated. Migrations are reversible where the
operation allows it. `Review` and `AuditLog` are append-only in code.

## accounts

**accounts_user** (custom model from day one)
`id` UUID PK · `display_name` · `role` (`founder|reviewer|admin`) · `is_active` ·
`is_staff` · `is_superuser` · `last_login` · `created_at` · `updated_at`.
No password login; SIWS only. `USERNAME_FIELD = id`.

**accounts_wallet**
`id` · `user` FK · `address` char(44) unique · `is_primary` · `linked_at`.
Unique (`user`,`address`).

**accounts_signin_challenge**
`id` · `nonce` unique · `domain` · `uri` · `chain_id` · `statement` ·
`issued_at` · `expires_at` · `consumed_at` · `wallet_address` · `request_ip_hash`.
Redis holds the authoritative single-use nonce; this row is the audit trail.

**accounts_refresh_token**
`id` · `user` FK · `token_hash` unique · `family_id` · `parent` FK self ·
`expires_at` · `revoked_at` · `replaced_by` FK self · `user_agent_hash`.
Reuse of a rotated token revokes the family.

## projects

**projects_founder_profile**: `user` OneToOne · `display_name` · `bio` · `website`.

**projects_category**: `slug` unique · `name`.

**projects_project**: `founder` FK · `name` · `slug` unique · `description` ·
`website` · `category` FK · `application_status` (draft, submitted, under_review,
approved, rejected) · `lifecycle_status` (active, completed, suspended) ·
`data_origin` (simulated, devnet, mainnet) · `review_notes` · `approved_at` ·
`approved_by` · `token_mint` (optional Mainnet mint) · `onchain_project_pda` · `chain_authority` · `chain_signature` ·
`chain_slot` · `chain_lifecycle_status`. `chain_authority` is set only after the
founder accepts the on-chain authority transfer. Check constraints on all enums.

**projects_application**: `project` FK · `submitted_at` · `reviewed_at` ·
`reviewer` · `decision` (pending, approved, rejected) · `notes`.

## milestones

**milestones_roadmap**: `project` FK · `title` · `description` · `order` ·
`created_by` · timestamps. Off-chain grouping for milestones.

**milestones_verification_criteria**: `id` · `version` · `criteria_hash` · `criteria_uri` ·
`published_by` · `published_at` · `active` · `onchain_template_pda` · `chain_signature`.
Admin-published, versioned, immutable criteria. `version >= 1`.

**milestones_milestone**: `project` FK · `roadmap` FK (nullable) · `title` · `description` · `deadline` ·
`status` (draft, submitted, under_review, verified, rejected) · `current_round` ·
`required_approvals` · `criteria_template` FK · `criteria_hash` · `criteria_uri` ·
`criteria_version` · `created_by` · `onchain_milestone_pda` · `chain_signature` ·
`chain_slot` · `chain_status`. `required_approvals >= 1`, `current_round >= 0`.
Overdue is derived, not stored. Public output omits milestones with
`required_approvals < 2`.

**milestones_submission**: `milestone` FK · `round` · `evidence_hash` bytea(32) ·
`evidence_uri` ≤128 · `criteria_hash` bytea(32) · `criteria_uri` ≤128 ·
`submitted_by` · `submitted_at` · `data_origin` · chain fields.
Unique (`milestone`,`round`), `round >= 1`.

## evidence

**evidence_evidence**: `submission` FK · `kind` (repo, document, url, file) · `uri` ·
`sha256` bytea(32) · `content_type` · `size_bytes` (≤25 MiB enforced in `clean`) ·
`data_origin`.

## reviews

**reviews_reviewer**: `user` OneToOne · `wallet_address` unique · `approved_by` ·
`approved_at` · `active` · `onchain_reviewer_pda` · `chain_signature`.

**reviews_assignment**: `milestone` FK · `reviewer` FK · `assigned_by` ·
`assigned_at` · `revoked_at` · `chain_signature`. Unique (`milestone`,`reviewer`).

**reviews_dispute**: `review` FK · `filed_by` · `reason` · `status`
(open/upheld/rejected) · `resolution` · `resolved_by` · `resolved_at`. The reason is
append-only; only resolution fields change.

**reviews_review** (append-only): `milestone` FK · `submission` FK · `round` ·
`reviewer` FK · `decision` (verify, reject) · `comment` · `criteria_hash` ·
`data_origin` · chain fields. Unique (`milestone`,`round`,`reviewer`).
`save()` rejects updates; `delete()` raises.

## chain

**chain_transaction**: `signature` · `instruction_index` · `program_id` · `slot` ·
`block_time` · `status` (pending, confirmed, failed) · `error` · `intent` ·
`object_type` · `object_id` · `payload` · `processed_at` · `data_origin`.
Unique (`signature`,`instruction_index`).

**chain_processed_signature**: (`signature`,`instruction_index`) unique · `slot` ·
`processed_at`.

**chain_indexer_cursor**: `name` unique · `last_signature` · `last_slot` ·
`updated_at`.

**chain_signed_intent**: `intent` · `object_type` · `object_id` · `payload` ·
`expires_at` · `consumed_at` · `data_origin`.

## integrations

**integrations_github_account**: `project` OneToOne · `linked_by` · `repo_url` ·
`repo_owner` · `repo_name` · `github_login` · `proof_method` · `verified_at` ·
`last_activity` JSONB · `activity_fetched_at`.

**integrations_github_challenge**: `user` · `project` · `repo_url` · `repo_owner` ·
`repo_name` · `nonce` unique · `message` · `expires_at` · `consumed_at`.

**integrations_token_cache**: `mint` unique · `name` · `symbol` · `payload` JSONB ·
`fetched_at` · `source`. Audit of the latest Jupiter snapshot; Redis is the hot cache.

## common

**common_audit_log** (append-only): `id` · `actor` · `action` · `object_type` ·
`object_id` (≤128) · `metadata` JSONB · `created_at`.

## Deliberately absent

Roadmap, Dispute, BuilderContribution, GitHubAccount, Token, Notification, treasury
and analytics tables. They arrive with their phases.
