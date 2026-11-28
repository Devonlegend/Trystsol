"""Single-use nonce storage backed by Redis.

Redis is authoritative for consumption: `GETDEL` makes a replay impossible even
under concurrent requests. The database row is the audit trail.
"""

from __future__ import annotations

import redis
from django.conf import settings

KEY_PREFIX = "trystsol:siws:nonce:"


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)


def store(nonce: str, challenge_id: str, ttl_seconds: int) -> None:
    _client().set(f"{KEY_PREFIX}{nonce}", challenge_id, ex=ttl_seconds)


def consume(nonce: str) -> bool:
    """Atomically remove the nonce. Returns True only for the first caller."""
    return _client().getdel(f"{KEY_PREFIX}{nonce}") is not None


def exists(nonce: str) -> bool:
    return bool(_client().exists(f"{KEY_PREFIX}{nonce}"))


def clear_all() -> None:
    """Test helper: remove only TrystSol nonce keys."""
    client = _client()
    for key in client.scan_iter(match=f"{KEY_PREFIX}*"):
        client.delete(key)
