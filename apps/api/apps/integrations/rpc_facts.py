"""Read-only Mainnet mint facts over JSON-RPC.

Jupiter token data is Mainnet, so mint facts must be read from a Mainnet endpoint.
Configure MAINNET_RPC_URL for a private endpoint; the public Mainnet RPC is the
fallback and is rate limited.
"""

from __future__ import annotations

import logging

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "trystsol:rpc:mint:"


class RpcFactError(Exception):
    pass


def _rpc_url() -> str:
    return settings.MAINNET_RPC_URL


def get_mint_facts(mint: str) -> dict:
    key = f"{CACHE_KEY}{mint}"
    cached = cache.get(key)
    if cached:
        return cached

    url = _rpc_url()
    if not url:
        raise RpcFactError("No Mainnet RPC configured.")
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
    }
    try:
        response = httpx.post(url, json=body, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("mainnet_rpc_transport_error")
        raise RpcFactError("Mainnet RPC request failed.") from exc
    if response.status_code != 200:
        raise RpcFactError(f"Mainnet RPC returned HTTP {response.status_code}.")
    payload = response.json()
    if payload.get("error"):
        raise RpcFactError(str(payload["error"].get("message", "RPC error")))
    value = (payload.get("result") or {}).get("value")
    if not value:
        return {
            "found": False,
            "mint": mint,
            "source": "Solana Mainnet RPC",
        }

    data = value.get("data") or {}
    parsed = data.get("parsed") if isinstance(data, dict) else None
    info = (parsed or {}).get("info") if isinstance(parsed, dict) else None
    if not isinstance(info, dict):
        raise RpcFactError("Mint account is not a parsed SPL mint.")

    facts = {
        "found": True,
        "mint": mint,
        "owner_program": value.get("owner"),
        "decimals": info.get("decimals"),
        "supply": info.get("supply"),
        "mint_authority": info.get("mintAuthority"),
        "freeze_authority": info.get("freezeAuthority"),
        "is_initialized": info.get("isInitialized"),
        "source": "Solana Mainnet RPC",
    }
    cache.set(key, facts, settings.RPC_FACT_CACHE_TTL)
    return facts
