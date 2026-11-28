# Phase 3 Report — Proof-of-Build

**Date:** 2026-11-28
**Status:** Phase 3 complete and verified on Devnet.

## Objective

Turn the reviewed-milestone slice into a usable proof-of-build workflow: roadmaps,
typed evidence, reviewer comments, disputes, resubmission history and a public
completion page.

## Delivered

### Roadmaps
- Off-chain roadmaps with title, description and order.
- Founders create and edit roadmaps; milestones may belong to one.
- Public and manage payloads list roadmaps and attach each milestone to its track.

### Evidence
- Submissions accept 1-10 evidence items, each with kind
  (`repo`, `document`, `url`, `file`), URI, SHA-256, optional content type and size.
- The first item's URI (≤128 bytes) and hash are anchored on-chain; all items are
  stored off-chain and published with the submission.
- Primary evidence URI length and kind are validated before an intent is prepared.
- Binary uploads are intentionally not accepted yet; `file` is a hosted reference.

### Reviews and history
- Reviewer comments are now entered in the dashboard and published with the verdict.
- Resubmission rounds, prior submissions and prior verifications remain visible.

### Completion percentage
- `progress.verified / progress.total` over **published** milestones only.
- Drafts and single-review (`R < 2`) milestones are excluded.
- The public page shows a progress bar and the plain basis:
  "Verified milestones divided by published milestones. No weighting, composite
  score or forecast."

### Disputes
- Any authenticated user can file a dispute on a published verdict with a reason.
- One open dispute per user per verdict.
- Admin resolves as `upheld` or `rejected` with a written resolution.
- Disputes are published next to the verdict; the on-chain verdict is unchanged.

### Tests and E2E
- **31 backend tests** (up from 29), including roadmap permissions, evidence
  validation, progress calculation, dispute filing/resolution and public output.
- Anchor tests remain **19 passing**; the program did not change.
- Indexer **5 passing**; web production build passes.
- Updated Devnet E2E: founder profile, roadmap, milestone, evidence list, two
  reviewers, verification, indexer backfill and public progress.

## Devnet E2E result

Project: `orbit-tools-devnet-e2e-9`

- progress: `1 of 1` published milestones verified, `100%`
- roadmap: `Indexer delivery`
- evidence: `repo` item anchored and published
- reviews: 2 (`verify`)
- first verification: `TN3iSeex2gG2NKYwLK83aK1u6UDZ3NoWvE6spm7JqqTXTZcbB6njGRC82K53HL9wA95JF9fTKiUAaLtGUVMJ6Ct`
- second verification: `5DoUJPefPoyVTJJAnecBWyQJauXKsE2JvF713iJ2W8weCG1QmPAPwb1MF2FPHeyFLNsRzKusFt592hqAsHWGZiKW`
- indexer cursor slot: `527210807`

## Open items

1. Approve Phase 4 (decision pages + Intelligence Engine integrations).
2. Manual Phantom wallet test.
3. Run CI on GitHub and confirm green.
4. Evidence upload pipeline (type allowlist, malware scan, separate origin) is
   Phase 5.
5. Admin dispute-resolution UI is API-only for now; public dispute display works.
6. Roadmap editing is API-only; the UI supports creation and selection.

## Next

Phase 4: GitHub repo-control proof, Jupiter read-only token data, on-chain facts via
RPC, the two-tier decision page, and the Builder Passport derived only from verified
milestones. Every fact must show its source, fetch time and a plain note about what
it does not tell you.
