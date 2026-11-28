# Phase 5 Report — Hardening

**Date:** 2026-11-28
**Status:** Phase 5 complete. The Devnet MVP is functionally complete and
demonstrated. Mainnet is not part of this phase.

## Objective

Security testing, UI polish, Devnet demonstration and documentation after Phases
0-4.

## Hardening delivered

### Sessions
- Refresh tokens moved to an `HttpOnly`, `SameSite=Lax` cookie scoped to
  `/api/auth/`; `Secure` when `DEBUG=false`.
- Access tokens are memory-only; the web app no longer persists tokens in
  `localStorage`.
- Page reload restores the session through the refresh cookie and `/api/auth/me/`.
- Refresh rotation/reuse detection and family revocation remain.
- Legacy `trystsol.session` storage is removed on the next save/clear.

### API protections
- General DRF throttles: anonymous 60/min, authenticated 240/min; auth endpoints
  remain 20/min per IP.
- Indexer endpoints bypass user throttles (shared-secret authenticated) while still
  requiring the secret.
- Evidence and criteria URIs must be http(s); `javascript:` and other schemes are
  rejected at the API.
- Public payloads suppress unsafe legacy URIs (defence in depth).
- Project website and GitHub repo URLs remain validated.
- CSRF exposure is reduced by the narrow cookie path, `SameSite=Lax` and CORS with
  explicit origins/credentials.

### Browser headers and staging stance
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` disables camera/microphone/geolocation.
- A limited CSP covers `frame-ancestors`, `object-src` and `base-uri`.
- `robots.txt` disallows all crawling; page metadata is `noindex, nofollow`.
- A visible Devnet test-data banner is shown on every page.

### Admin and disputes
- Admin dispute list endpoint and dashboard UI for `upheld`/`rejected` resolutions.
- Public dispute display remains next to the immutable verdict.

### Documentation
- `docs/RUNBOOK.md` for start/stop, deploy, E2E, backups, key rotation and audits.
- ADR-0016 records the session design.
- SECURITY, API, architecture, schema and status updated.

## Verification

| Check | Result |
|---|---|
| Backend/integration tests | **47 passed** |
| Anchor tests | 19 passed |
| Indexer tests | 5 passed |
| Web production build | passed |
| Compose stack | healthy |
| Security headers | present |
| `robots.txt` | disallow all |
| Devnet E2E | passed |

Final Devnet demonstration: `orbit-tools-devnet-e2e-10`

- two reviewers, `R = 2`
- roadmap, multi-item evidence
- milestone verified
- public progress `1 of 1`, `100%`
- JUP Mainnet mint attached for the decision page
- second verification signature `3CBgsTBuX2WCAVQtBfRabs1HMwzM4t4m94oG3MteHjjVbzUeCYBTMjkCjShaiLPqyduPVi95RXTzGqnooVoAgq4v`
- indexer cursor slot `527220169`

Public pages verified:

- project decision page (`/projects/orbit-tools-devnet-e2e-10`)
- token decision page (`/tokens/<JUP mint>`)
- Builder Passport (`/builders/<founder-id>`)
- Jupiter + Mainnet mint automated facts with source/time/caveat

## Residual risks

- Access tokens remain usable by an XSS while the tab is open; the CSP is
  intentionally limited and does not define `script-src` yet.
- Evidence binary uploads are not accepted; only links/hashes. A future upload
  pipeline needs type allowlists, malware scanning and separate-origin downloads.
- GitHub repo proof has been tested with mocked content, not a live commit.
- Mainnet RPC falls back to the public endpoint; configure a private endpoint.
- The program is unaudited; the admin/deploy key is a single Devnet key.
- No streaming, alerts, rankings, treasury views or Mainnet deployment.
- Phantom manual test and a real GitHub repository proof remain human tasks.

## Next

Stop for a human pilot/business decision. Phase 6 (Jupiter Studio launches) remains
blocked by Gate S: legal advice, Jupiter API/Devnet/earnings answers, and a passed
pilot/business gate. Mainnet deployment, audit and multisig are out of scope until a
human explicitly approves them.
