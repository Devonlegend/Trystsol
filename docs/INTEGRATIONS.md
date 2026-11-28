# Integrations — Phase 4

Last reviewed: 2026-11-28. All external calls are server-side and read-only.

## Jupiter

Sources read 2026-11-24:

- Token API: `https://api.jup.ag/tokens/v2/search`
- Price API: `https://api.jup.ag/price/v3`
- Rate limits: keyless 0.5 req/s; free with key 1 req/s (60/min); 60-second
  sliding window.

Implementation:

- `apps/integrations/jupiter.py`.
- One key covers all Jupiter APIs; sent only as `x-api-key` from the server.
- Token search is limited to the exact mint; the response must contain that mint.
- Price supports one mint per request here.
- Redis cache: 300 seconds per mint for token and price data.
- HTTP 429: one delayed retry, then a structured error. No aggressive retry loop.
- `TokenCache` records the latest token snapshot for audit.
- Displayed fields are Jupiter's data, with source, fetch time and caveats:
  `isVerified`, `organicScore`/label, holder count, mint/freeze authority flags,
  top-holder percentage, market data.
- Jupiter data is **Mainnet**. A project must supply a Mainnet mint; the page
  labels it as Mainnet data.
- Never present Jupiter's verification or Organic Score as a TrystSol verdict.

## On-chain mint facts

- `apps/integrations/rpc_facts.py`.
- Reads the mint account with `getAccountInfo` (`jsonParsed`) from
  `MAINNET_RPC_URL`.
- Default is the public Mainnet RPC; configure a private endpoint for production.
- Facts: supply, decimals, mint authority, freeze authority, owner program.
- Redis cache: 300 seconds.
- Failure or a missing account becomes an explicit "unavailable" fact with a
  caveat, not a page error.

## GitHub

Sources read 2026-11-24:

- REST API rate limits: unauthenticated 60/h; authenticated 5,000/h; secondary
  limits return 403/429. Use a GitHub App/OAuth token in `GITHUB_TOKEN` for
  production; unauthenticated is only for development.
- Contents API: `GET /repos/{owner}/{repo}/contents/{path}`.

Repo-control proof (signed file):

1. The founder requests a challenge for a project and repo URL.
2. The API returns a message containing wallet, canonical repo URL, nonce and
   issued-at.
3. The founder signs it with the linked wallet and commits
   `.trystsol/proof.json` containing `address`, `message`, `signature` (base64).
4. The API fetches the file from the repository default branch, verifies the exact
   message and Ed25519 signature, and records `GitHubAccount`.

Security constraints:

- Only `github.com` URLs are accepted, parsed into a strict owner/repo pattern.
- The server never fetches a user-supplied URL directly; it calls
  `api.github.com/repos/{owner}/{repo}/...` only.
- This proves commit control, not repository administration or project ownership.
- Repository URL alone never counts as proof.
- Activity cache: 900 seconds; stars, forks, open issues, pushed-at and commits in
  the last 30 days (one API page, capped at 100 and labelled).
- 403/429: one delayed retry, then a structured error.

## Decision pages

- `apps/decision_pages/services.py`.
- Two tiers: `reviewed` (Phase 3 project payload) and `automated_sections`.
- Every automated fact includes `source`, `source_url`, `fetched_at` and `caveat`.
- Token-only pages show automated facts and explicitly state that no reviewed
  claims are attached.
- No ranking, featured list, buy/avoid signal, TrystSol score or composite metric.
- Price/market fields are Jupiter's data and labelled as not a TrystSol price view.

## Builder Passport

- `apps/passport/services.py`.
- Derived only from verified milestones with at least two approvals.
- Includes project, milestone title, round, verification time, reviewers and chain
  signatures.
- No score, rating or reputation number.
