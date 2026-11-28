# ADR-0014: Off-chain roadmap, evidence and dispute records

- **Status:** Accepted (Phase 3)
- **Date:** 2026-11-28

## Context

Phase 3 adds planning and accountability records around the on-chain milestone
verdict. The chain stores hashes and URIs only, and must stay small and neutral.

## Decision

1. **Roadmaps are off-chain.** A roadmap is a titled, ordered delivery track for a
   project. Milestones may optionally belong to one. The program does not know about
   roadmaps, so roadmap edits never require a transaction or change a verdict.
2. **Completion is a published-milestone ratio.** `percentage = verified / published
   milestones`, where published means at least two required approvals and not a
   draft. It is labelled with its basis and is not weighted, scored or forecast.
3. **Evidence is multi-item off-chain state with a single on-chain anchor.** A
   submission accepts up to 10 evidence items (`repo`, `document`, `url`, `file`),
   each with a SHA-256 and optional content type/size. The first item's URI (≤128
   bytes) and hash are written on-chain; all items are stored off-chain.
   Binary uploads are not accepted yet; `file` is a reference to a hosted file.
4. **Disputes are off-chain and append-only in their reason.** Any authenticated
   user may file a dispute on a published verdict; one open dispute per user per
   verdict. An admin resolves it as `upheld` or `rejected` with a written
   resolution. The on-chain verdict is not altered; the dispute is published next to
   it.
5. **Review comments are published.** The reviewer comment is stored in the
   append-only Review and shown with the verdict.

## Consequences

- Roadmaps, evidence and disputes can evolve without program upgrades.
- The public page can show 100% only when every published milestone is verified; it
  never implies future delivery or safety.
- Dispute reasons and resolutions are public; no private documents should be placed
  there.
- A future evidence-upload pipeline needs type allowlists, malware scanning,
  separate-origin downloads and retention rules (Phase 5).
