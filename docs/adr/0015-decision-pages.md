# ADR-0015: Decision pages, automated facts and Builder Passport

- **Status:** Accepted (Phase 4)
- **Date:** 2026-11-28

## Context

Phase 4 adds the Intelligence Engine: sourced facts about a project or token with
no human review, shown next to the reviewed claims. Jupiter is Mainnet-only while
the registry is on Devnet, and GitHub proof must not introduce an SSRF surface.

## Decision

1. **Two tiers, visibly separate.** The decision payload returns `reviewed`
   (Phase 3 project payload) and `automated_sections` (Jupiter, Mainnet mint, GitHub).
   The UI labels automated facts as having no human review.
2. **Every fact carries source, source URL, fetch time and caveat.** No fact is shown
   without them. Failures become explicit unavailable facts, not page errors.
3. **No TrystSol score or rating.** Jupiter's `isVerified` and Organic Score are
   displayed as Jupiter's data with caveats. Market data is Jupiter's data and is not
   a TrystSol price view, forecast or buy/avoid signal. No rankings or discovery
   feeds are created.
4. **Mainnet/Devnet separation.** Jupiter and mint facts are Mainnet data; the
   registry is Devnet. The page states this. A project supplies an optional Mainnet
   mint; if absent, automated token sections are omitted.
5. **Read-only, server-side integrations.** Jupiter/GitHub/Mainnet RPC calls happen
   only in Django. Keys are server-side environment variables. Redis caches with TTLs
   protect rate limits.
6. **GitHub proof is a signed file in the repo.** The server verifies an Ed25519
   signature over a challenge message containing the wallet and canonical repo URL.
   It fetches only `api.github.com/repos/{owner}/{repo}/contents/.trystsol/proof.json`
   for a strictly parsed `github.com` URL. This proves commit control, not admin
   rights or project ownership.
7. **Builder Passport is derived, not scored.** It lists verified milestones with at
   least two approvals, their reviewers and chain signatures. No reputation number.

## Consequences

- Decision pages can be useful on day one for any token with a mint, even without
  reviewed claims.
- Rate limits and outages degrade to caveated unavailable facts rather than false
  data.
- A private Mainnet RPC and GitHub token are recommended for production.
- Evidence/reviewed claims remain the differentiator; automated facts never imply a
  TrystSol verdict.
- Streaming, alerts, rankings and treasury views remain deferred.
