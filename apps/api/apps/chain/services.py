from __future__ import annotations

import datetime as dt
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog
from apps.milestones.models import Milestone, MilestoneStatus, MilestoneSubmission
from apps.projects.models import ApplicationStatus, Project
from apps.reviews.models import Review, ReviewDecision, Reviewer, ReviewerAssignment

from . import rpc
from .models import BlockchainTransaction, SignedIntent, TransactionStatus

logger = logging.getLogger(__name__)


class IntentError(Exception):
    def __init__(self, message: str, code: str = "intent_invalid"):
        super().__init__(message)
        self.code = code


INTENT_TTL_SECONDS = 900


def prepare_intent(
    *,
    intent: str,
    object_type: str,
    object_id: uuid.UUID,
    payload: dict,
) -> SignedIntent:
    return SignedIntent.objects.create(
        intent=intent,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        expires_at=timezone.now() + dt.timedelta(seconds=INTENT_TTL_SECONDS),
    )


def serialize_intent(intent: SignedIntent) -> dict:
    return {
        "id": str(intent.id),
        "intent": intent.intent,
        "object_type": intent.object_type,
        "object_id": str(intent.object_id),
        "payload": intent.payload,
        "expires_at": intent.expires_at,
    }


def _wallet_for(user) -> str | None:
    wallet = user.wallets.filter(is_primary=True).first() or user.wallets.first()
    return wallet.address if wallet else None


def _validate_transaction(
    tx: dict,
    *,
    expected_signer: str,
    expected_pda: str | None,
) -> tuple[int, int | None]:
    meta = tx.get("meta")
    if meta is None:
        raise IntentError("Transaction metadata is missing.", "tx_missing_meta")
    if meta.get("err") is not None:
        raise IntentError("Transaction failed on-chain.", "tx_failed")

    message = tx.get("transaction", {}).get("message", {})
    account_keys = message.get("accountKeys")
    if not isinstance(account_keys, list) or not account_keys:
        raise IntentError("Transaction has no account keys.", "tx_malformed")
    if not isinstance(account_keys[0], str):
        account_keys = [item.get("pubkey") for item in account_keys]

    header = message.get("header", {})
    required_signatures = int(header.get("numRequiredSignatures", 1))
    signer_keys = account_keys[:required_signatures]
    if expected_signer not in signer_keys:
        raise IntentError("Transaction was not signed by the expected wallet.", "tx_wrong_signer")
    if expected_pda and expected_pda not in account_keys:
        raise IntentError("Transaction does not touch the expected account.", "tx_wrong_account")

    program_id = settings.PROGRAM_ID
    instructions = message.get("instructions", [])
    touches_program = False
    for instruction in instructions:
        index = instruction.get("programIdIndex")
        if isinstance(index, int) and 0 <= index < len(account_keys):
            if account_keys[index] == program_id:
                touches_program = True
                break
    if not touches_program:
        raise IntentError("Transaction does not invoke the TrystSol program.", "tx_wrong_program")

    slot = tx.get("slot")
    block_time = tx.get("blockTime")
    if slot is None:
        raise IntentError("Transaction slot is missing.", "tx_malformed")
    return int(slot), block_time


@transaction.atomic
def confirm_intent(*, intent_id: uuid.UUID, signature: str, user):
    try:
        intent = SignedIntent.objects.select_for_update().get(pk=intent_id)
    except SignedIntent.DoesNotExist as exc:
        raise IntentError("Unknown intent.", "intent_unknown") from exc

    existing = BlockchainTransaction.objects.filter(
        signature=signature, instruction_index=0, status=TransactionStatus.CONFIRMED
    ).first()
    if existing is not None and intent.consumed_at is not None:
        return existing  # Idempotent replay of a confirmed intent.

    if intent.consumed_at is not None:
        raise IntentError("Intent has already been confirmed.", "intent_consumed")
    if intent.expires_at <= timezone.now():
        raise IntentError("Intent has expired; prepare a new transaction.", "intent_expired")

    expected_signer = intent.payload.get("signer")
    actor_wallet = _wallet_for(user)
    if not expected_signer or actor_wallet != expected_signer:
        raise IntentError("This intent must be confirmed by a different wallet.", "intent_wrong_signer")

    try:
        tx = rpc.get_transaction(signature)
    except rpc.RpcError as exc:
        raise IntentError(str(exc), "rpc_error") from exc
    if tx is None:
        raise IntentError("Transaction not found yet; retry after confirmation.", "tx_not_found")

    slot, block_time = _validate_transaction(
        tx,
        expected_signer=expected_signer,
        expected_pda=intent.payload.get("account"),
    )
    block_dt = (
        dt.datetime.fromtimestamp(block_time, tz=dt.timezone.utc) if block_time else None
    )

    record, _created = BlockchainTransaction.objects.update_or_create(
        signature=signature,
        instruction_index=0,
        defaults={
            "program_id": settings.PROGRAM_ID,
            "slot": slot,
            "block_time": block_dt,
            "status": TransactionStatus.CONFIRMED,
            "intent": intent.intent,
            "object_type": intent.object_type,
            "object_id": intent.object_id,
            "payload": intent.payload,
            "processed_at": timezone.now(),
        },
    )

    intent.consumed_at = timezone.now()
    intent.save(update_fields=["consumed_at", "updated_at"])

    apply_intent(intent, signature=signature, slot=slot)
    AuditLog.objects.create(
        actor=user,
        action=f"chain.{intent.intent}.confirmed",
        object_type=intent.object_type,
        object_id=str(intent.object_id),
        metadata={"signature": signature, "slot": slot},
    )
    return record


def apply_intent(intent: SignedIntent, *, signature: str, slot: int) -> None:
    handler = {
        "project.register": _apply_project_register,
        "project.accept_authority": _apply_project_accept_authority,
        "criteria.publish": _apply_criteria_publish,
        "reviewer.deactivate": _apply_reviewer_deactivate,
        "milestone.expire": _apply_milestone_expire,
        "milestone.create": _apply_milestone_create,
        "milestone.assign": _apply_milestone_assign,
        "milestone.submit": _apply_milestone_submit,
        "milestone.verdict": _apply_milestone_verdict,
        "reviewer.add": _apply_reviewer_add,
    }.get(intent.intent)
    if handler is None:
        raise IntentError(f"No handler for intent {intent.intent}.", "intent_unknown")
    handler(intent, signature=signature, slot=slot)


def _apply_project_register(intent: SignedIntent, *, signature: str, slot: int) -> None:
    project = Project.objects.select_for_update().get(pk=intent.object_id)
    if project.application_status != ApplicationStatus.APPROVED:
        raise IntentError("Project is not approved.", "project_not_approved")
    project.onchain_project_pda = intent.payload["project_pda"]
    project.chain_signature = signature
    project.chain_slot = slot
    project.chain_lifecycle_status = "active"
    # The admin registered it; the founder must accept authority separately.
    project.chain_authority = ""
    project.save(
        update_fields=[
            "onchain_project_pda",
            "chain_signature",
            "chain_slot",
            "chain_lifecycle_status",
            "chain_authority",
            "updated_at",
        ]
    )

    founder_wallet = intent.payload.get("founder")
    if not founder_wallet:
        raise IntentError("Registration payload is missing the founder wallet.", "payload_invalid")
    prepare_intent(
        intent="project.accept_authority",
        object_type="project",
        object_id=project.id,
        payload={
            "instruction": "accept_authority_transfer",
            "program_id": settings.PROGRAM_ID,
            "signer": founder_wallet,
            "account": project.onchain_project_pda,
            "args": {},
            "accounts": {
                "pending_authority": founder_wallet,
                "project": project.onchain_project_pda,
            },
        },
    )


def _apply_project_accept_authority(intent: SignedIntent, *, signature: str, slot: int) -> None:
    project = Project.objects.select_for_update().get(pk=intent.object_id)
    project.chain_authority = intent.payload["signer"]
    project.save(update_fields=["chain_authority", "updated_at"])


def _apply_criteria_publish(intent: SignedIntent, *, signature: str, slot: int) -> None:
    from apps.milestones.models import VerificationCriteria

    criteria = VerificationCriteria.objects.select_for_update().get(pk=intent.object_id)
    criteria.onchain_template_pda = intent.payload["criteria_pda"]
    criteria.chain_signature = signature
    criteria.save(update_fields=["onchain_template_pda", "chain_signature", "updated_at"])


def _apply_reviewer_deactivate(intent: SignedIntent, *, signature: str, slot: int) -> None:
    reviewer = Reviewer.objects.select_for_update().get(pk=intent.object_id)
    reviewer.active = False
    reviewer.save(update_fields=["active", "updated_at"])


def _apply_milestone_expire(intent: SignedIntent, *, signature: str, slot: int) -> None:
    milestone = Milestone.objects.select_for_update().get(pk=intent.object_id)
    milestone.status = MilestoneStatus.REJECTED
    milestone.chain_signature = signature
    milestone.chain_slot = slot
    milestone.chain_status = MilestoneStatus.REJECTED
    milestone.save(
        update_fields=["status", "chain_signature", "chain_slot", "chain_status", "updated_at"]
    )


def _apply_milestone_create(intent: SignedIntent, *, signature: str, slot: int) -> None:
    milestone = Milestone.objects.select_for_update().get(pk=intent.object_id)
    milestone.onchain_milestone_pda = intent.payload["milestone_pda"]
    milestone.chain_signature = signature
    milestone.chain_slot = slot
    milestone.save(
        update_fields=["onchain_milestone_pda", "chain_signature", "chain_slot", "updated_at"]
    )


def _apply_milestone_assign(intent: SignedIntent, *, signature: str, slot: int) -> None:
    milestone = Milestone.objects.select_for_update().get(pk=intent.object_id)
    internal = intent.payload.get("internal", {})
    reviewer_ids = internal.get("reviewer_ids", [])
    for reviewer_id in reviewer_ids:
        reviewer = Reviewer.objects.get(pk=reviewer_id, active=True)
        ReviewerAssignment.objects.get_or_create(
            milestone=milestone,
            reviewer=reviewer,
            defaults={
                "assigned_by_id": internal["assigned_by"],
                "chain_signature": signature,
            },
        )
    AuditLog.objects.create(
        action="milestone.reviewers_assigned",
        object_type="milestone",
        object_id=str(milestone.id),
        metadata={"signature": signature, "slot": slot, "reviewers": reviewer_ids},
    )


def _apply_milestone_submit(intent: SignedIntent, *, signature: str, slot: int) -> None:
    milestone = Milestone.objects.select_for_update().get(pk=intent.object_id)
    internal = intent.payload["internal"]
    round_number = int(internal["round"])
    if not milestone.criteria_hash:
        raise IntentError("Milestone has no fixed criteria.", "criteria_missing")
    evidence_items = internal.get("evidence") or []
    if not evidence_items:
        raise IntentError("Submission has no evidence.", "evidence_missing")
    primary = evidence_items[0]
    submission, created = MilestoneSubmission.objects.get_or_create(
        milestone=milestone,
        round=round_number,
        defaults={
            "evidence_hash": bytes.fromhex(primary["sha256"]),
            "evidence_uri": primary["uri"],
            "criteria_hash": milestone.criteria_hash,
            "criteria_uri": milestone.criteria_uri,
            "submitted_by_id": internal["submitted_by"],
            "chain_signature": signature,
            "chain_slot": slot,
        },
    )
    if not created:
        raise IntentError("Submission for this round already exists.", "submission_exists")
    from apps.evidence.models import Evidence

    for item in evidence_items:
        Evidence.objects.create(
            submission=submission,
            kind=item["kind"],
            uri=item["uri"],
            sha256=bytes.fromhex(item["sha256"]),
            content_type=item.get("content_type", ""),
            size_bytes=item.get("size_bytes", 0),
        )
    milestone.current_round = round_number
    milestone.status = MilestoneStatus.SUBMITTED
    milestone.chain_signature = signature
    milestone.chain_slot = slot
    milestone.chain_status = "submitted"
    milestone.save(
        update_fields=[
            "current_round",
            "status",
            "chain_signature",
            "chain_slot",
            "chain_status",
            "updated_at",
        ]
    )


def _apply_milestone_verdict(intent: SignedIntent, *, signature: str, slot: int) -> None:
    milestone = Milestone.objects.select_for_update().get(pk=intent.object_id)
    internal = intent.payload["internal"]
    submission = MilestoneSubmission.objects.get(
        milestone=milestone, round=int(internal["round"])
    )
    reviewer = Reviewer.objects.get(pk=internal["reviewer_id"])
    decision = ReviewDecision(internal["decision"])

    Review.objects.create(
        milestone=milestone,
        submission=submission,
        round=submission.round,
        reviewer=reviewer,
        decision=decision,
        comment=internal.get("comment", ""),
        criteria_hash=submission.criteria_hash,
        chain_signature=signature,
        chain_slot=slot,
    )

    approvals = milestone.reviews.filter(round=submission.round, decision=ReviewDecision.VERIFY).count()
    rejections = milestone.reviews.filter(round=submission.round, decision=ReviewDecision.REJECT).count()
    reviewer_count = milestone.reviewer_assignments.filter(revoked_at__isnull=True).count()
    required = milestone.required_approvals
    if reviewer_count < required or required < 1:
        raise IntentError("Milestone reviewer configuration is invalid.", "milestone_invalid")

    if approvals >= required:
        milestone.status = MilestoneStatus.VERIFIED
    elif rejections >= reviewer_count - required + 1:
        milestone.status = MilestoneStatus.REJECTED
    else:
        milestone.status = MilestoneStatus.UNDER_REVIEW
    milestone.chain_signature = signature
    milestone.chain_slot = slot
    milestone.chain_status = milestone.status
    milestone.save(
        update_fields=["status", "chain_signature", "chain_slot", "chain_status", "updated_at"]
    )


def _apply_reviewer_add(intent: SignedIntent, *, signature: str, slot: int) -> None:
    reviewer = Reviewer.objects.select_for_update().get(pk=intent.object_id)
    reviewer.onchain_reviewer_pda = intent.payload["reviewer_pda"]
    reviewer.chain_signature = signature
    reviewer.save(update_fields=["onchain_reviewer_pda", "chain_signature", "updated_at"])
