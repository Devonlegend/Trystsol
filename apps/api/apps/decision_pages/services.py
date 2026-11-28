"""Decision-page read model: automated facts next to reviewed claims.

Every fact carries a source, source URL, fetch time and a plain caveat. No TrystSol
rating, ranking or composite score is computed or shown.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils import timezone

from apps.integrations import github, jupiter, rpc_facts
from apps.projects.services import public_project_payload

NOTICES = [
    "Information only. This page is not investment advice.",
    "Automated facts have no human review and are not TrystSol verdicts.",
    "Jupiter token data is Mainnet data; the TrystSol registry runs on Devnet.",
    "A fact's source and fetch time are shown with it. Check the source before relying on it.",
]


def _fact(
    *,
    key: str,
    label: str,
    value: Any,
    source: str,
    source_url: str,
    caveat: str,
    fetched_at: dt.datetime,
) -> dict:
    return {
        "key": key,
        "label": label,
        "value": value,
        "source": source,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "caveat": caveat,
    }


def _unavailable(
    *, key: str, label: str, source: str, source_url: str, error: str, fetched_at: dt.datetime
) -> dict:
    return _fact(
        key=key,
        label=label,
        value=None,
        source=source,
        source_url=source_url,
        caveat=f"Unavailable: {error}",
        fetched_at=fetched_at,
    )


def jupiter_section(mint: str) -> dict:
    now = timezone.now()
    source_url = f"https://jup.ag/tokens/{mint}"
    try:
        snapshot = jupiter.token_snapshot(mint)
    except jupiter.IntegrationError as exc:
        return {
            "id": "jupiter",
            "tier": "automated",
            "title": "Jupiter token data (Mainnet)",
            "facts": [
                _unavailable(
                    key="jupiter.available",
                    label="Jupiter token data",
                    source="Jupiter Token API",
                    source_url=source_url,
                    error=str(exc),
                    fetched_at=now,
                )
            ],
        }

    token = snapshot["token"]
    price = snapshot["price"]
    audit = token.get("audit") or {}
    facts = [
        _fact(
            key="jupiter.identity",
            label="Token identity (Jupiter)",
            value={
                "name": token.get("name"),
                "symbol": token.get("symbol"),
                "mint": token.get("mint"),
                "decimals": token.get("decimals"),
            },
            source="Jupiter Token API",
            source_url=source_url,
            caveat="Jupiter's metadata. A symbol can be claimed by any mint; use the mint address.",
            fetched_at=now,
        ),
        _fact(
            key="jupiter.is_verified",
            label="Jupiter verification",
            value=token.get("isVerified"),
            source="Jupiter Token API",
            source_url=source_url,
            caveat=(
                "Jupiter's own review, not an endorsement or a TrystSol verdict. "
                "Unverified tokens may still be legitimate; verified is not a safety guarantee."
            ),
            fetched_at=now,
        ),
        _fact(
            key="jupiter.organic_score",
            label="Jupiter Organic Score",
            value={
                "score": token.get("organicScore"),
                "label": token.get("organicScoreLabel"),
            },
            source="Jupiter Token API",
            source_url=source_url,
            caveat=(
                "Jupiter's relative 0-100 measure of organic trading activity; volatile for "
                "fresh tokens. This is not a TrystSol score, rating or signal."
            ),
            fetched_at=now,
        ),
        _fact(
            key="jupiter.holder_count",
            label="Holder count (Jupiter)",
            value=token.get("holderCount"),
            source="Jupiter Token API",
            source_url=source_url,
            caveat="A count from Jupiter; it does not describe distribution, control or wallet identity.",
            fetched_at=now,
        ),
        _fact(
            key="jupiter.audit",
            label="Mint and freeze authority flags (Jupiter)",
            value={
                "mint_authority_disabled": audit.get("mintAuthorityDisabled"),
                "freeze_authority_disabled": audit.get("freezeAuthorityDisabled"),
                "top_holders_percentage": audit.get("topHoldersPercentage"),
                "is_sus": audit.get("isSus"),
            },
            source="Jupiter Token API",
            source_url=source_url,
            caveat=(
                "Jupiter's flags. A disabled authority or absent flag is not proof of safety, "
                "and holder concentration is not a verdict."
            ),
            fetched_at=now,
        ),
    ]
    if price:
        facts.append(
            _fact(
                key="jupiter.price",
                label="Jupiter market data",
                value={
                    "usd_price": price.get("usdPrice"),
                    "price_change_24h": price.get("priceChange24h"),
                    "liquidity": price.get("liquidity"),
                    "block_id": price.get("blockId"),
                },
                source="Jupiter Price API",
                source_url=source_url,
                caveat=(
                    "Jupiter's market data at the shown block; it is not a TrystSol price view, "
                    "forecast or buy/avoid signal."
                ),
                fetched_at=now,
            )
        )
    elif snapshot.get("price_error"):
        facts.append(
            _unavailable(
                key="jupiter.price",
                label="Jupiter market data",
                source="Jupiter Price API",
                source_url=source_url,
                error=snapshot["price_error"],
                fetched_at=now,
            )
        )
    return {
        "id": "jupiter",
        "tier": "automated",
        "title": "Jupiter token data (Mainnet)",
        "facts": facts,
    }


def mint_section(mint: str) -> dict:
    now = timezone.now()
    source_url = f"https://explorer.solana.com/address/{mint}"
    try:
        facts = rpc_facts.get_mint_facts(mint)
    except rpc_facts.RpcFactError as exc:
        return {
            "id": "mint",
            "tier": "automated",
            "title": "On-chain mint facts (Mainnet)",
            "facts": [
                _unavailable(
                    key="mint.available",
                    label="Mint account",
                    source="Solana Mainnet RPC",
                    source_url=source_url,
                    error=str(exc),
                    fetched_at=now,
                )
            ],
        }

    if not facts.get("found"):
        return {
            "id": "mint",
            "tier": "automated",
            "title": "On-chain mint facts (Mainnet)",
            "facts": [
                _fact(
                    key="mint.found",
                    label="Mint account",
                    value=False,
                    source="Solana Mainnet RPC",
                    source_url=source_url,
                    caveat="No mint account was found at this address on Mainnet.",
                    fetched_at=now,
                )
            ],
        }

    return {
        "id": "mint",
        "tier": "automated",
        "title": "On-chain mint facts (Mainnet)",
        "facts": [
            _fact(
                key="mint.supply",
                label="Supply and decimals",
                value={"supply": facts.get("supply"), "decimals": facts.get("decimals")},
                source="Solana Mainnet RPC",
                source_url=source_url,
                caveat="On-chain supply. It does not imply value, distribution or delivery.",
                fetched_at=now,
            ),
            _fact(
                key="mint.authorities",
                label="Mint and freeze authorities",
                value={
                    "mint_authority": facts.get("mint_authority"),
                    "freeze_authority": facts.get("freeze_authority"),
                    "owner_program": facts.get("owner_program"),
                },
                source="Solana Mainnet RPC",
                source_url=source_url,
                caveat=(
                    "Authorities can change supply or freeze accounts. A null authority is not "
                    "a guarantee of safety."
                ),
                fetched_at=now,
            ),
        ],
    }


def github_section(project) -> dict | None:
    account = getattr(project, "github_account", None)
    if account is None:
        return None
    now = timezone.now()
    since = (now - dt.timedelta(days=30)).isoformat()
    try:
        activity = github.fetch_activity(account.repo_owner, account.repo_name, since)
    except github.GitHubError as exc:
        return {
            "id": "github",
            "tier": "automated",
            "title": "GitHub repository activity",
            "facts": [
                _unavailable(
                    key="github.available",
                    label="GitHub repository activity",
                    source="GitHub REST API",
                    source_url=account.repo_url,
                    error=str(exc),
                    fetched_at=now,
                )
            ],
        }

    commits = activity.get("commits_since")
    commit_caveat = (
        "At least 100 commits were returned; the count is capped by one API page."
        if activity.get("commits_since_capped")
        else "Commits returned by one GitHub API page."
    )
    return {
        "id": "github",
        "tier": "automated",
        "title": "GitHub repository activity",
        "facts": [
            _fact(
                key="github.repository",
                label="Repository",
                value={
                    "full_name": activity.get("full_name"),
                    "archived": activity.get("archived"),
                    "visibility": activity.get("visibility"),
                    "default_branch": activity.get("default_branch"),
                },
                source="GitHub REST API",
                source_url=account.repo_url,
                caveat=(
                    "Control was proven by a signed file committed to the repository. "
                    "This proves commit control, not ownership of the project or admin rights."
                ),
                fetched_at=now,
            ),
            _fact(
                key="github.activity",
                label="Stars, forks and open issues",
                value={
                    "stars": activity.get("stargazers_count"),
                    "forks": activity.get("forks_count"),
                    "open_issues": activity.get("open_issues_count"),
                    "pushed_at": activity.get("pushed_at"),
                },
                source="GitHub REST API",
                source_url=account.repo_url,
                caveat="Repository popularity and issue counts do not prove delivery or quality.",
                fetched_at=now,
            ),
            _fact(
                key="github.commits",
                label="Commits in the last 30 days",
                value=commits,
                source="GitHub REST API",
                source_url=account.repo_url,
                caveat=commit_caveat + " Commit activity is not a delivery verdict.",
                fetched_at=now,
            ),
        ],
    }


def build_project_decision(project) -> dict:
    sections = []
    if project.token_mint:
        sections.append(jupiter_section(project.token_mint))
        sections.append(mint_section(project.token_mint))
    github_data = github_section(project)
    if github_data:
        sections.append(github_data)
    return {
        "project": project.slug,
        "generated_at": timezone.now(),
        "reviewed": public_project_payload(project),
        "automated_sections": sections,
        "notices": NOTICES,
    }


def build_token_decision(mint: str) -> dict:
    return {
        "mint": mint,
        "generated_at": timezone.now(),
        "automated_sections": [jupiter_section(mint), mint_section(mint)],
        "notices": [
            "Information only. This page is not investment advice.",
            "Jupiter data is Mainnet data and has no human review by TrystSol.",
            "No reviewed claims are attached to this token.",
        ],
    }
