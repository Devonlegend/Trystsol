"""Read-only declared treasury wallet view.

This is not custody and does not prove ownership. It shows the SOL balance and
recent transaction signatures for a wallet the project declares, with the chain,
source and fetch time.
"""

from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

WALLET_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
CACHE_KEY = "trystsol:treasury:"

CAVEATS = [
    "This wallet is declared by the project; TrystSol has not proven ownership or control.",
    "Only SOL is shown. Token balances are not priced or valued here.",
    "Recent transactions are a short signature list, not a full accounting.",
    "TrystSol never holds, moves or releases these funds.",
]


class TreasuryError(Exception):
    pass


def _rpc_url(chain: str) -> str:
    if chain == "mainnet":
        return settings.MAINNET_RPC_URL
    return settings.SERVER_RPC_URL or settings.SOLANA_RPC_URL


def _rpc(url: str, method: str, params: list) -> object:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        response = httpx.post(url, json=body, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("treasury_rpc_transport_error", extra={"method": method})
        raise TreasuryError("Treasury RPC request failed.") from exc
    if response.status_code != 200:
        raise TreasuryError(f"Treasury RPC returned HTTP {response.status_code}.")
    payload = response.json()
    if payload.get("error"):
        raise TreasuryError(str(payload["error"].get("message", "RPC error")))
    return payload.get("result")


def get_treasury_snapshot(wallet: str, chain: str) -> dict:
    if not WALLET_RE.match(wallet or ""):
        raise TreasuryError("Invalid treasury wallet address.")
    if chain not in ("devnet", "mainnet"):
        raise TreasuryError("Invalid treasury chain.")
    key = f"{CACHE_KEY}{chain}:{wallet}"
    cached = cache.get(key)
    if cached:
        return cached

    url = _rpc_url(chain)
    if not url:
        raise TreasuryError("No RPC configured for this chain.")

    balance_result = _rpc(url, "getBalance", [wallet, {"commitment": "confirmed"}])
    lamports = int((balance_result or {}).get("value", 0))
    signatures = _rpc(
        url,
        "getSignaturesForAddress",
        [wallet, {"limit": 10, "commitment": "confirmed"}],
    )
    if not isinstance(signatures, list):
        signatures = []

    snapshot = {
        "linked": True,
        "wallet": wallet,
        "chain": chain,
        "balance_lamports": lamports,
        "balance_sol": lamports / 1_000_000_000,
        "recent_transactions": [
            {
                "signature": item.get("signature"),
                "slot": item.get("slot"),
                "block_time": item.get("blockTime"),
                "err": item.get("err") is not None,
            }
            for item in signatures
            if isinstance(item, dict)
        ],
        "source": "Solana Devnet RPC" if chain == "devnet" else "Solana Mainnet RPC",
        "source_url": f"https://explorer.solana.com/address/{wallet}"
        + ("?cluster=devnet" if chain == "devnet" else ""),
        "fetched_at": timezone.now(),
        "caveats": CAVEATS,
    }
    cache.set(key, snapshot, settings.TREASURY_CACHE_TTL)
    return snapshot
