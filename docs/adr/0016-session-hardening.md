# ADR-0016: Browser session hardening

- **Status:** Accepted (Phase 5)
- **Date:** 2026-11-28

## Context

Phase 0-4 stored access and refresh tokens in `localStorage`. Any XSS could read and
exfiltrate a long-lived refresh token. Phase 5 must remove that persistence.

## Decision

- The **refresh token** is set by the API as an `HttpOnly`, `SameSite=Lax` cookie,
  scoped to `/api/auth/`. It is `Secure` when `DEBUG=false`.
- The **access token** is kept in browser memory only; it is not persisted to
  `localStorage` or `sessionStorage`.
- On page load, the web app calls `POST /api/auth/refresh/` with the cookie, then
  fetches `/api/auth/me/` to rebuild the in-memory session.
- Refresh rotation and reuse detection remain unchanged. Logout revokes the family
  and clears the cookie.
- CORS uses explicit origins with `Access-Control-Allow-Credentials: true`.
- The API still returns a refresh token in the JSON response for non-browser API
  clients and tests; the web app ignores it and never stores it.
- Legacy `trystsol.session` entries from earlier builds are removed when the web app
  next saves or clears a session.

## Consequences

- An XSS can use the in-memory access token for its short lifetime but cannot read
  or persist the refresh token.
- `SameSite=Lax` plus the narrow cookie path reduces cross-site exposure. The web
  app must use `localhost:8000` for the API and be served from `localhost:3000` so
  the cookie is same-site (ports do not affect site).
- Production requires HTTPS so the cookie is `Secure`.
- Native/API clients continue to use the JSON refresh token.
- Residual risk: a script executing in the page can still call APIs while the tab
  is open; CSP and dependency hygiene remain important.
