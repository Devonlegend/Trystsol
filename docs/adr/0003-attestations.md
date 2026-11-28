# ADR-0003: Verification records — custom program only, SAS deferred

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

The Solana Attestation Service (SAS) provides credentials, schemas and attestations. Its documentation and GitHub README (read 2026-11-24) state that attestation accounts can be **closed to revoke** them and may carry an expiry. The brief requires that verification history is never deleted and that a resubmission keeps earlier records.

## Options

1. Custom `project_registry` program only.
2. Custom program plus SAS attestations as the public credential.
3. SAS only.

## Decision

Option 1 for Phases 0-3. Project, milestone and verification state live in the custom program. SAS is deferred.

## Reasons

- SAS revocation conflicts with permanent verification history; the custom program's `Verification` PDA keyed by milestone + round + reviewer is append-only in practice.
- SAS adds credential and schema management plus a second program to index, with no Phase 0 user benefit.
- The brief's default is custom program for state, SAS deferred.

## Revisit if

A funder or third-party application requires a standard credential format, or cross-program consumption of verdicts becomes a requirement. That requires a new ADR and a design where the custom program stays authoritative.
