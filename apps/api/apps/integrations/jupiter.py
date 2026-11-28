"""Jupiter Token and Price APIs (read-only, Mainnet data).

Docs read 2026-11-24:
- https://dev.jup.ag/docs/tokens (api.jup.ag/tokens/v2/search, up to 100 mints)
- https://dev.jup.ag/docs/price-api (api.jup.ag/price/v3, up to 50 ids)
- https://dev.jup.ag/docs/portal/rate-limits (keyless 0.5 rps, free 1 rps)
"""

from __future__ import annotations

import logging
import re
import time

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import TokenCache

logger = logging.getLogger(__name__)

MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
TOKEN_CACHE_KEY = "trystsol:jup:token:"
PRICE_CACHE_KEY = "trystsol:jup:price:"


class IntegrationError(Exception):
    pass


def _validate_mint(mint: str) -> None:
    if not MINT_RE.match(mint or ""):
        raise IntegrationError("Invalid token mint.")


def _headers() -> dict:
    if settings.JUPITER_API_KEY:
        return {"x-api-key": settings.JUPITER_API_KEY}
    return {}


def _get(path: str, params: dict) -> object:
    url = f"{settings.JUPITER_BASE_URL.rstrip('/')}{path}"
    for attempt in range(2):
        try:
            response = httpx.get(url, params=params, headers=_headers(), timeout=10.0)
        except httpx.HTTPError as exc:
            logger.warning("jupiter_transport_error", extra={"path": path})
            raise IntegrationError("Jupiter request failed.") from exc
        if response.status_code == 429 and attempt == 0:
            time.sleep(1.0)
            continue
        if response.status_code != 200:
            logger.warning(
                "jupiter_http_error",
                extra={"status": response.status_code, "path": path},
            )
            raise IntegrationError(f"Jupiter returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationError("Jupiter returned invalid JSON.") from exc
    raise IntegrationError("Jupiter rate limit persisted.")


def fetch_token(mint: str) -> dict:
    _validate_mint(mint)
    key = f"{TOKEN_CACHE_KEY}{mint}"
    cached = cache.get(key)
    if cached:
        return cached

    payload = _get("/tokens/v2/search", {"query": mint})
    if not isinstance(payload, list):
        raise IntegrationError("Unexpected Jupiter token response.")
    token = next(
        (item for item in payload if isinstance(item, dict) and item.get("id") == mint),
        None,
    )
    if token is None:
        raise IntegrationError("Jupiter does not know this mint.")

    selected = {
        "mint": token.get("id"),
        "name": token.get("name"),
        "symbol": token.get("symbol"),
        "decimals": token.get("decimals"),
        "isVerified": token.get("isVerified"),
        "organicScore": token.get("organicScore"),
        "organicScoreLabel": token.get("organicScoreLabel"),
        "holderCount": token.get("holderCount"),
        "usdPrice": token.get("usdPrice"),
        "mcap": token.get("mcap"),
        "liquidity": token.get("liquidity"),
        "audit": token.get("audit") or {},
        "tags": token.get("tags") or [],
    }
    cache.set(key, selected, settings.JUPITER_CACHE_TTL)
    TokenCache.objects.update_or_create(
        mint=mint,
        defaults={
            "name": selected.get("name") or "",
            "symbol": selected.get("symbol") or "",
            "payload": selected,
            "fetched_at": timezone.now(),
            "source": "jupiter",
        },
    )
    return selected


def fetch_price(mint: str) -> dict | None:
    _validate_mint(mint)
    key = f"{PRICE_CACHE_KEY}{mint}"
    cached = cache.get(key)
    if cached is not None:
        return cached or None

    payload = _get("/price/v3", {"ids": mint})
    if not isinstance(payload, dict):
        raise IntegrationError("Unexpected Jupiter price response.")
    price = payload.get(mint)
    cache.set(key, price or {}, settings.JUPITER_CACHE_TTL)
    return price or None


def token_snapshot(mint: str) -> dict:
    token = fetch_token(mint)
    price = None
    price_error = None
    try:
        price = fetch_price(mint)
    except IntegrationError as exc:
        price_error = str(exc)
        logger.info("jupiter_price_unavailable", extra={"mint": mint})
    return {"token": token, "price": price, "price_error": price_error}
