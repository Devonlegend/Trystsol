from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import nonce_store
from .models import SignInChallenge, User, UserRole, Wallet
from .siws import SIWSError, parse_message, verify_message
from .tokens import issue_token_pair


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_challenge(*, request_ip_hash: str = "") -> SignInChallenge:
    now = timezone.now().replace(microsecond=0)
    expires_at = now + dt.timedelta(seconds=settings.SIWS_NONCE_TTL_SECONDS)
    challenge = SignInChallenge.objects.create(
        nonce=__import__("secrets").token_hex(16),
        domain=settings.SIWS_DOMAIN,
        uri=settings.SIWS_URI,
        chain_id=settings.SIWS_CHAIN_ID,
        statement=settings.SIWS_STATEMENT,
        issued_at=now,
        expires_at=expires_at,
        request_ip_hash=request_ip_hash,
    )
    nonce_store.store(challenge.nonce, str(challenge.id), settings.SIWS_NONCE_TTL_SECONDS)
    return challenge


def challenge_payload(challenge: SignInChallenge) -> dict:
    return {
        "domain": challenge.domain,
        "uri": challenge.uri,
        "version": "1",
        "chainId": challenge.chain_id,
        "nonce": challenge.nonce,
        "statement": challenge.statement,
        "issuedAt": _iso(challenge.issued_at),
        "expirationTime": _iso(challenge.expires_at),
    }


def verify_and_issue(*, message: str, signature, user_agent_hash: str = "") -> tuple[User, Wallet, dict]:
    """Verify a SIWS message, consume its nonce, and issue tokens.

    The challenge is looked up from the nonce inside the signed message; the client
    cannot choose which fields to compare.
    """
    parsed = parse_message(message)

    try:
        challenge = SignInChallenge.objects.get(nonce=parsed.nonce)
    except SignInChallenge.DoesNotExist as exc:
        raise SIWSError("Unknown or expired nonce.") from exc

    now = timezone.now()
    if challenge.consumed_at is not None:
        raise SIWSError("Nonce has already been used.")
    if challenge.expires_at <= now:
        raise SIWSError("Challenge has expired.")

    address = verify_message(
        message,
        signature,
        challenge,
        now=now,
        issued_at_skew_seconds=settings.SIWS_ISSUED_AT_SKEW_SECONDS,
    )

    # Atomic single-use check. Only the first concurrent caller succeeds.
    if not nonce_store.consume(parsed.nonce):
        raise SIWSError("Nonce has already been used or expired.")

    with transaction.atomic():
        locked = SignInChallenge.objects.select_for_update().get(pk=challenge.pk)
        if locked.consumed_at is not None:
            raise SIWSError("Nonce has already been used.")
        locked.consumed_at = now
        locked.wallet_address = address
        locked.save(update_fields=["consumed_at", "wallet_address", "updated_at"])

        wallet = Wallet.objects.select_related("user").filter(address=address).first()
        if wallet is None:
            user = User.objects.create_user(role=UserRole.FOUNDER)
            wallet = Wallet.objects.create(user=user, address=address, is_primary=True)
        else:
            user = wallet.user
            if not user.is_active:
                raise SIWSError("User is inactive.")

        tokens = issue_token_pair(user, address, user_agent_hash=user_agent_hash)

    return user, wallet, tokens
