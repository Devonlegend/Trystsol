from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from django.conf import settings
from django.utils import timezone

from .models import RefreshToken


class TokenError(Exception):
    pass


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_access_token(user, wallet_address: str) -> str:
    now = timezone.now()
    payload = {
        "sub": str(user.id),
        "wallet": wallet_address,
        "role": user.role,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=settings.ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.ACCESS_TOKEN_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.ACCESS_TOKEN_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Access token is invalid.") from exc
    if payload.get("typ") != "access":
        raise TokenError("Wrong token type.")
    return payload


def issue_refresh_token(
    user,
    *,
    family_id: uuid.UUID | None = None,
    parent: RefreshToken | None = None,
    user_agent_hash: str = "",
) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    record = RefreshToken.objects.create(
        user=user,
        token_hash=_hash(raw),
        family_id=family_id or uuid.uuid4(),
        parent=parent,
        expires_at=timezone.now() + dt.timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        user_agent_hash=user_agent_hash,
    )
    return raw, record


def issue_token_pair(user, wallet_address: str, *, user_agent_hash: str = "") -> dict:
    refresh_raw, _ = issue_refresh_token(user, user_agent_hash=user_agent_hash)
    return {
        "access": issue_access_token(user, wallet_address),
        "refresh": refresh_raw,
        "token_type": "Bearer",
        "expires_in": settings.ACCESS_TOKEN_TTL_SECONDS,
    }


def rotate_refresh(raw_token: str, *, user_agent_hash: str = "") -> dict:
    record = RefreshToken.objects.filter(token_hash=_hash(raw_token)).select_related("user").first()
    if record is None:
        raise TokenError("Refresh token is invalid.")

    if record.revoked_at is not None:
        # Reuse of an already-rotated token: assume compromise and revoke the family.
        RefreshToken.objects.filter(family_id=record.family_id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        raise TokenError("Refresh token has already been used.")

    if record.expires_at <= timezone.now():
        raise TokenError("Refresh token has expired.")

    wallet = record.user.wallets.filter(is_primary=True).first() or record.user.wallets.first()
    if wallet is None:
        raise TokenError("User has no linked wallet.")

    new_raw, new_record = issue_refresh_token(
        record.user,
        family_id=record.family_id,
        parent=record,
        user_agent_hash=user_agent_hash,
    )
    record.revoked_at = timezone.now()
    record.replaced_by = new_record
    record.save(update_fields=["revoked_at", "replaced_by", "updated_at"])

    return {
        "access": issue_access_token(record.user, wallet.address),
        "refresh": new_raw,
        "token_type": "Bearer",
        "expires_in": settings.ACCESS_TOKEN_TTL_SECONDS,
    }


def revoke_refresh(raw_token: str) -> None:
    record = RefreshToken.objects.filter(token_hash=_hash(raw_token)).first()
    if record is None:
        return
    RefreshToken.objects.filter(family_id=record.family_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
