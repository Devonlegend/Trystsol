from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import secrets

from django.db import transaction
from django.utils import timezone
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from apps.accounts.siws import SIWSError, b58decode
from apps.common.models import AuditLog

from . import github
from .models import GitHubAccount, GitHubProofChallenge

PROOF_PATH = github.PROOF_PATH
CHALLENGE_TTL_SECONDS = 900


class ProofError(Exception):
    def __init__(self, message: str, code: str = "github_proof_invalid"):
        super().__init__(message)
        self.code = code


def _proof_message(*, wallet: str, repo_url: str, nonce: str, issued_at: str) -> str:
    return (
        "TrystSol repository proof\n"
        f"Wallet: {wallet}\n"
        f"Repository: {repo_url}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}"
    )


def _primary_wallet(user) -> str | None:
    wallet = user.wallets.filter(is_primary=True).first() or user.wallets.first()
    return wallet.address if wallet else None


def create_challenge(user, project, repo_url: str) -> GitHubProofChallenge:
    if project.founder_id != user.id and not user.is_admin:
        raise ProofError("Only the founder can prove repository control.", "forbidden")
    try:
        owner, repo, canonical = github.parse_repo_url(repo_url)
    except github.GitHubError as exc:
        raise ProofError(str(exc), "repo_invalid") from exc

    wallet = _primary_wallet(user)
    if not wallet:
        raise ProofError("Link a wallet before proving a repository.", "wallet_missing")

    now = timezone.now().replace(microsecond=0)
    nonce = secrets.token_hex(16)
    issued_at = now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    message = _proof_message(wallet=wallet, repo_url=canonical, nonce=nonce, issued_at=issued_at)
    challenge = GitHubProofChallenge.objects.create(
        user=user,
        project=project,
        repo_url=canonical,
        repo_owner=owner,
        repo_name=repo,
        nonce=nonce,
        message=message,
        expires_at=now + dt.timedelta(seconds=CHALLENGE_TTL_SECONDS),
    )
    AuditLog.objects.create(
        actor=user,
        action="github.challenge_created",
        object_type="github_challenge",
        object_id=str(challenge.id),
        metadata={"repo": canonical},
    )
    return challenge


@transaction.atomic
def verify_challenge(user, challenge: GitHubProofChallenge) -> GitHubAccount:
    challenge = GitHubProofChallenge.objects.select_for_update().get(pk=challenge.pk)
    if challenge.user_id != user.id:
        raise ProofError("This challenge belongs to another user.", "forbidden")
    if challenge.consumed_at is not None:
        raise ProofError("Challenge already used.", "challenge_used")
    if challenge.expires_at <= timezone.now():
        raise ProofError("Challenge expired; create a new one.", "challenge_expired")

    wallet = _primary_wallet(user)
    if not wallet:
        raise ProofError("Link a wallet before proving a repository.", "wallet_missing")

    try:
        raw = github.fetch_file(challenge.repo_owner, challenge.repo_name, PROOF_PATH)
    except github.GitHubNotFound as exc:
        raise ProofError(
            f"Proof file {PROOF_PATH} was not found in the repository default branch.",
            "proof_missing",
        ) from exc
    except github.GitHubError as exc:
        raise ProofError(str(exc), "github_error") from exc

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise ProofError("Proof file is not valid JSON.", "proof_invalid") from exc
    if not isinstance(payload, dict):
        raise ProofError("Proof file must be a JSON object.", "proof_invalid")

    address = payload.get("address")
    message = payload.get("message")
    signature = payload.get("signature")
    if address != wallet or message != challenge.message or not isinstance(signature, str):
        raise ProofError("Proof file does not match this wallet and challenge.", "proof_mismatch")

    try:
        signature_bytes = base64.b64decode(signature + "=" * (-len(signature) % 4), validate=True)
        verify_key = VerifyKey(b58decode(address))
        verify_key.verify(message.encode("utf-8"), signature_bytes)
    except (binascii.Error, ValueError, SIWSError, BadSignatureError) as exc:
        raise ProofError("Proof signature is invalid.", "proof_signature") from exc

    try:
        repo = github.fetch_repo(challenge.repo_owner, challenge.repo_name)
    except github.GitHubError as exc:
        raise ProofError(str(exc), "github_error") from exc

    account, _ = GitHubAccount.objects.update_or_create(
        project=challenge.project,
        defaults={
            "linked_by": user,
            "repo_url": challenge.repo_url,
            "repo_owner": challenge.repo_owner,
            "repo_name": challenge.repo_name,
            "github_login": repo.get("owner") or "",
            "proof_method": "signed_file",
            "verified_at": timezone.now(),
            "last_activity": {},
            "activity_fetched_at": None,
        },
    )
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at", "updated_at"])
    AuditLog.objects.create(
        actor=user,
        action="github.repo_verified",
        object_type="github_account",
        object_id=str(account.id),
        metadata={"repo": challenge.repo_url},
    )
    return account
