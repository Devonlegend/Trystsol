# ADR-0005: Toolchain versions and pinning

- **Status:** Accepted (Phase 0)
- **Date:** 2026-11-25

## Context

The brief requires pinning versions in lockfiles and `Anchor.toml [toolchain]`. Official docs were read on 2026-11-24. The machine had Anchor 1.2.0 installed outside AVM and Solana CLI 4.2.2. Devnet reported cluster version 4.5.0-beta.0.

## Decision

| Tool | Version | Source |
|---|---|---|
| Anchor CLI | 1.2.2 (via AVM) | Official Anchor installation docs |
| anchor-lang / anchor-spl | 1.2.2 | crates.io |
| `@anchor-lang/core` | 1.2.2 | npm |
| Solana CLI / platform tools | 4.2.2 | pinned in `Anchor.toml [toolchain]` |
| Node.js | 22.x (LTS) | local |
| Python | 3.14.x | local; Django 6.1 classifiers list 3.14 |
| Rust | 1.89.0 | Anchor 1.2 MSRV is 1.89 |

Install commands used:

```bash
cargo install --git https://github.com/otter-sec/anchor avm --force
avm install 1.2.2
avm use 1.2.2
```

## Rationale

1.2.2 (released 2026-10-22) contains macro-hygiene and key-validation fixes absent from 1.2.0. Anchor 2.0.0-rc.2 is a release candidate and is not used for a security-sensitive program.

## Consequences

- `Anchor.toml` pins `anchor_version = "1.2.2"` and `solana_version = "4.2.2"`.
- Devnet runs a newer cluster version than the local CLI; the first Devnet deploy is a compatibility test and its result is recorded in `DEVELOPMENT_STATUS.md`.
- Upgrading any pinned tool requires a new ADR and a full test run.
