"""Minimal Solana JSON-RPC client for server-side confirmation.

Only read calls are made. Transactions are built and signed by the user's wallet;
the server never holds a signing key in Phase 0.
"""

from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

SIGNATURE_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,88}$")


class RpcError(Exception):
    pass


def _call(method: str, params: list) -> dict:
    url = settings.SERVER_RPC_URL
    if not url:
        raise RpcError("No server RPC URL configured.")
    try:
        response = httpx.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("rpc_transport_error", extra={"error_code": "rpc_transport"})
        raise RpcError("RPC request failed.") from exc
    if response.status_code != 200:
        raise RpcError(f"RPC returned HTTP {response.status_code}.")
    body = response.json()
    if body.get("error"):
        raise RpcError(str(body["error"].get("message", "RPC error")))
    return body.get("result")


def get_transaction(signature: str) -> dict | None:
    if not SIGNATURE_RE.match(signature):
        raise RpcError("Invalid transaction signature.")
    return _call(
        "getTransaction",
        [
            signature,
            {
                "encoding": "json",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )


def get_account_info(address: str) -> dict | None:
    result = _call("getAccountInfo", [address, {"encoding": "base64", "commitment": "confirmed"}])
    return (result or {}).get("value")


def get_signatures_for_program(program_id: str, *, limit: int = 25, before: str | None = None) -> list[dict]:
    options: dict = {"limit": min(max(limit, 1), 100), "commitment": "confirmed"}
    if before:
        options["before"] = before
    return _call("getSignaturesForAddress", [program_id, options]) or []


def get_health() -> str:
    result = _call("getHealth", [])
    return str(result)
