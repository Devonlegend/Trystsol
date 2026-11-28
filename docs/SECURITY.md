# Security — Phase 0

Devnet only. No real-money flows. The program is unaudited.

## Implemented controls

### Authentication
- SIWS message parsing is strict: canonical header/address/statement/field order,
  no duplicate or unknown fields, LF-only, canonical base58, 32-byte key.
- Every field is compared with the **server-issued challenge**, not with
  client-supplied copies.
- Ed25519 verification with PyNaCl.
- Nonce consumption is atomic in Redis (`GETDEL`), so a replay loses even under
  concurrent requests. The database row is an audit trail and a second check.
- Domain, URI, chain id, issued-at skew (10 minutes) and expiry are enforced.
- Short-lived access JWT (15 minutes) and rotating opaque refresh tokens; reuse of
  a rotated token revokes the whole family.
- The refresh token is set as an `HttpOnly`, `SameSite=Lax` cookie scoped to
  `/api/auth/` (Secure when `DEBUG=false`). The web app keeps the access token in
  memory only and restores the session from the cookie on reload.
- Nonce and verification endpoints are IP-throttled (20/min).
- General API throttles: anonymous 60/min, authenticated 240/min. Indexer endpoints
  use the shared secret and bypass user throttles.
- Wallets without `signIn` use `connect + signMessage` with the same SIWS message.

### Authorisation
- Two-step project authority: the admin registers, but the founder must sign
  `accept_authority_transfer` from their own wallet before milestone work. No
  server-held key signs for either party.
- Admin-published criteria templates: founders select a version, they cannot
  choose or edit the criteria content. Submission accepts only evidence.
- Published verdicts require at least two required approvals; public output hides
  any legacy `R = 1` milestone.
- Role checks in views: admin-only decisions, reviewer registry, assignment,
  criteria publication, reviewer deactivation and round expiry; founder ownership
  for project and milestone actions.
- The program independently enforces admin gating, reviewer assignment and
  authority self-review prevention.
- Off-chain checks mirror the program (founder cannot review their own milestone,
  one verdict per reviewer per round, reviewer must be active and assigned, no
  reassignment after a verdict, `R >= 2` for published verdicts).
- A stuck round can be expired by the admin and retried with a fresh reviewer set;
  history is preserved.

### Chain confirmation
- The server fetches the transaction from RPC and checks: `meta.err == null`,
  expected program id, expected signer among required signers, expected PDA among
  account keys, slot present.
- Transactions are idempotent on `(signature, instruction_index)`.
- Failed transactions are skipped by the indexer.
- `chain_*` fields are written only by confirmation or indexing.

### Phase 4 external reads
- Jupiter and Mainnet RPC calls are server-side only; keys never reach the browser.
- Jupiter/price data is cached in Redis with short TTLs and 429s back off once.
- GitHub repo URLs are strictly parsed to `github.com/<owner>/<repo>`; the server
  fetches only `api.github.com/repos/.../contents/.trystsol/proof.json`, never an
  arbitrary user URL. This is the SSRF boundary.
- GitHub proof verifies an Ed25519 signature over a challenge containing the wallet
  and canonical repo; it proves commit control, not admin rights.
- Automated facts are explicitly non-reviewed and never presented as TrystSol
  verdicts. No ranking/score is computed.

### Data
- `Review` and `AuditLog` are append-only in code. Dispute reasons are append-only;
  only the resolution fields change, by an admin.
- Evidence is stored as links, hashes, content types and sizes. Binary uploads are
  not accepted yet; the upload pipeline with type allowlist, malware scan and
  separate-origin downloads is Phase 5.
- Dispute reasons and resolutions are public. Do not place private documents or
  personal data in them.
- Evidence uploads are not accepted yet; only links/hashes are stored, avoiding
  SSRF and malware exposure in Phase 0.
- No personal data on-chain. Only hashes and URIs.
- `data_origin` labels simulated/devnet/mainnet records.
- Evidence and criteria URIs must be http(s); unsafe schemes are rejected and legacy
  unsafe URIs are suppressed in public payloads. React escapes reviewer comments and
  dispute text; no user HTML/SVG is rendered.
- The web app sends `X-Frame-Options`, `nosniff`, a strict referrer policy,
  permissions policy and a limited CSP; `robots.txt` disallows crawling and pages are
  `noindex` while on Devnet/staging.

### Deployment and CI
- Production (`DJANGO_ENV=production`) fails closed on default/short secrets,
  empty or wildcard `ALLOWED_HOSTS`, empty CORS, http origins or a localhost SIWS
  domain. It enables HSTS, secure cookies and SSL redirect.
- CI runs backend tests, Anchor tests, indexer tests, web build, `pip-audit`,
  `npm audit --audit-level=high` and `cargo audit` (two dev-only advisories
  allowlisted with a written rationale in ADR-0011).
- Docker images exclude `.env`; public RPC/API values use build-time
  `NEXT_PUBLIC_*`, while private RPC keys stay in `SERVER_RPC_URL` at runtime.

### Secrets
- Secrets come from environment variables. `.env` and keypairs are gitignored.
- Jupiter keys (Phase 4) must stay server-side.
- A private RPC URL (for example Helius) is a credential. It lives only in
  `SERVER_RPC_URL`, is used by the API and indexer, and is never placed in a
  `NEXT_PUBLIC_*` variable or shipped to the browser.
- The indexer authenticates to the API with a shared secret compared in constant
  time.

## Known gaps (must be closed before Phase 5/public launch)

1. **Access token in memory.** An XSS can use it while the tab is open; the refresh
   token is httpOnly. The CSP does not yet define `script-src`, so dependency and
   output hygiene remain important.
2. **Admin hot key.** The Devnet registry admin is a local keypair
   (`~/.config/solana/id.json`). It is not a multisig. Mainnet is out of scope, and
   the admin must become a multisig first.
4. **Rate limiting is auth-only.** General API endpoints rely on the PaaS/WAF;
   add per-user limits in Phase 5.
5. **No evidence upload pipeline.** Phase 3 must add type allowlist, size caps,
   malware scanning, separate-origin downloads, and no inline HTML/SVG.
6. **No SSRF surface yet.** Phase 4 fetches GitHub/Jupiter only from allowlisted
   hosts, never arbitrary user URLs. If a user-supplied URL is ever fetched,
   implement resolve-then-connect checks, private-range blocking, redirect/size/
   time caps, and an egress-restricted worker.
7. **Indexer snapshot endpoint trusts account snapshots.** It is authenticated by
   a shared secret and only writes `chain_*` fields, but a compromised worker could
   lie about chain state. Reconciliation against RPC is a Phase 5 hardening item.
8. **Legal publication review.** Decision-page publication of named tokens is
   Devnet/staging-only until the Gate S legal advice is recorded.

## Honest limits

- The program cannot know that two wallets belong to one person. Reviewer
  independence depends on the admin-managed registry and conflict declarations.
- Verification means the published criteria were met for the submitted evidence.
  It is not an endorsement, a safety rating or a guarantee of future delivery.
- Public labels must stay neutral, sourced and timestamped. Rejections are
  published like approvals. A dispute path is required before any public verdict;
  Phase 0 links to a placeholder process.

## Threat notes

- **Replay:** nonce is single-use in Redis and marked consumed in Postgres.
- **Phishing/domain binding:** the SIWS domain is fixed server-side.
- **Forged chain intent:** the server checks the expected signer and PDA on-chain.
- **Project squatting:** on-chain registration is admin-gated (ADR-0007).
- **Self-review:** blocked on-chain against `project.authority` and off-chain
  against the founder user.
- **Verdict deletion:** Verification PDAs are never closed; database Reviews have
  no update/delete path.
