# Phase 4 Report — Decision Pages and Integrations

**Date:** 2026-11-28
**Status:** Phase 4 complete. Read-only integrations and public decision pages are
live against Mainnet data.

## Objective

Add the Intelligence Engine: sourced facts with no human review, shown next to the
reviewed claims, plus a Builder Passport derived only from verified milestones.

## Delivered

### Jupiter (read-only)
- Token metadata, Jupiter verification, Organic Score, holder count, audit flags
  and market data from the Jupiter Token and Price APIs.
- Server-side only; key from `JUPITER_API_KEY`; 300-second Redis cache; 429 retry.
- Displayed as Jupiter's Mainnet data with source, fetch time and caveats.

### Mainnet mint facts
- Supply, decimals, mint authority, freeze authority and owner program read with
  `getAccountInfo` (`jsonParsed`) from `MAINNET_RPC_URL`.
- 300-second cache. Failures become explicit unavailable facts.

### GitHub
- Signed-file repo-control proof: challenge message with wallet + canonical repo,
  Ed25519 signature, committed `.trystsol/proof.json`, server verification through
  the GitHub Contents API.
- Strict `github.com` owner/repo parsing; no arbitrary URL fetch.
- Repo activity: stars, forks, open issues, pushed-at and commits in the last 30
  days; 900-second cache.
- Optional `GITHUB_TOKEN` raises the rate limit from 60/h to 5,000/h.

### Decision pages
- `GET /api/decision/projects/<slug>/` returns the reviewed claims and automated
  sections.
- `GET /api/decision/tokens/<mint>/` returns automated facts only and states that no
  reviewed claims are attached.
- Web pages: project decision facts, `/tokens/[mint]`, `/builders/[id]`.
- Every fact shows source, source URL, fetch time and caveat.
- No TrystSol rating, ranking, buy/avoid signal, composite score or discovery feed.

### Builder Passport
- Derived from verified milestones with at least two approvals.
- Shows project, milestone, round, verification time, reviewers and chain
  signatures. No score.

### Project controls
- Mainnet token mint can be set by the founder/admin from the manage page.
- GitHub proof challenge, signing, commit instructions and verification are in the
  manage page.

## Verification

| Check | Result |
|---|---|
| Backend/integration tests | **46 passed** |
| Anchor tests | 19 passed (unchanged) |
| Indexer tests | 5 passed |
| Web build | passed; new `tokens/[mint]` and `builders/[id]` routes |
| Live Jupiter + Mainnet RPC | passed on the JUP mint |

Live decision check on project `orbit-tools-devnet-e2e-9` with the JUP Mainnet mint:

- Jupiter identity: Jupiter / JUP / 6 decimals
- Jupiter verification: true
- Jupiter Organic Score: 97.58 (`high`) — labelled Jupiter's data
- Holder count: 835,558
- Market data: price, 24h change, liquidity from Jupiter
- Mint supply/decimals: read from Mainnet RPC
- Mint/freeze authority: null (shown with caveat)
- Reviewed claims: 1 of 1 published milestones verified, 100%

## Limitations

- Live GitHub repo proof was not executed against a real repository in this phase;
  the flow is covered by signed-file tests with mocked GitHub content. The human
  must commit `.trystsol/proof.json` to a repository.
- The Mainnet RPC falls back to the public endpoint; a private Mainnet RPC is
  recommended for production.
- Jupiter keyless/free limits apply; configure `JUPITER_API_KEY` for production.
- No streaming, alerts, rankings or discovery feeds (deferred).
- No treasury views (D3 default A).
- The project program remains Devnet-only and unaudited.

## Next

Phase 5: security testing, UI polish, Devnet demonstration, documentation, and the
evidence-upload hardening pipeline. Mainnet is not part of Phase 5.
