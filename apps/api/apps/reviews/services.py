from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.chain import pdas
from apps.chain.services import prepare_intent
from apps.common.models import AuditLog
from apps.milestones.models import Milestone, MilestoneStatus
from apps.milestones.services import milestone_id_hex

from .models import Dispute, DisputeStatus, Review, ReviewDecision, Reviewer, ReviewerAssignment

logger = logging.getLogger(__name__)


class ReviewError(Exception):
    def __init__(self, message: str, code: str = "review_invalid"):
        super().__init__(message)
        self.code = code


def _wallet_for(user) -> str | None:
    wallet = user.wallets.filter(is_primary=True).first() or user.wallets.first()
    return wallet.address if wallet else None


@transaction.atomic
def register_reviewer(admin, wallet_address: str):
    if not admin.is_admin:
        raise ReviewError("Administrator role required.", "forbidden")
    from apps.accounts.models import UserRole, Wallet

    wallet = Wallet.objects.select_related("user").filter(address=wallet_address).first()
    if wallet is None:
        raise ReviewError(
            "No user has signed in with that wallet. The reviewer must sign in first.",
            "wallet_unknown",
        )
    user = wallet.user
    admin_wallet = _wallet_for(admin)
    if not admin_wallet:
        raise ReviewError("Admin has no linked wallet.", "wallet_missing")

    existing = Reviewer.objects.filter(wallet_address=wallet_address).first()
    if existing and existing.onchain_reviewer_pda:
        raise ReviewError("Reviewer already registered on-chain.", "reviewer_exists")

    user.role = UserRole.REVIEWER
    user.save(update_fields=["role", "updated_at"])

    if existing:
        # A previous appointment was prepared but never confirmed; re-prepare it.
        reviewer = existing
        reviewer.approved_by = admin
        reviewer.approved_at = timezone.now()
        reviewer.active = True
        reviewer.save(update_fields=["approved_by", "approved_at", "active", "updated_at"])
    else:
        reviewer = Reviewer.objects.create(
            user=user,
            wallet_address=wallet_address,
            approved_by=admin,
            approved_at=timezone.now(),
            active=True,
        )
    reviewer_address = pdas.reviewer_pda(wallet_address)
    intent = prepare_intent(
        intent="reviewer.add",
        object_type="reviewer",
        object_id=reviewer.id,
        payload={
            "instruction": "add_reviewer",
            "program_id": settings.PROGRAM_ID,
            "signer": admin_wallet,
            "account": reviewer_address,
            "reviewer_pda": reviewer_address,
            "args": {"wallet": wallet_address},
            "accounts": {
                "admin": admin_wallet,
                "registry": pdas.registry_pda(),
                "reviewer": reviewer_address,
                "system_program": "11111111111111111111111111111111",
            },
        },
    )
    AuditLog.objects.create(
        actor=admin,
        action="reviewer.registered",
        object_type="reviewer",
        object_id=str(reviewer.id),
        metadata={"wallet": wallet_address},
    )
    return reviewer, intent


@transaction.atomic
def submit_verdict(user, milestone: Milestone, *, decision: str, comment: str = ""):
    try:
        reviewer = Reviewer.objects.get(user=user, active=True)
    except Reviewer.DoesNotExist as exc:
        raise ReviewError("Active reviewer profile required.", "forbidden") from exc

    milestone = (
        Milestone.objects.select_for_update()
        .select_related("project")
        .get(pk=milestone.pk)
    )
    if milestone.project.founder_id == user.id:
        raise ReviewError("A project founder cannot review their own milestone.", "self_review")
    if milestone.required_approvals < 2:
        raise ReviewError(
            "Published verdicts require at least two required approvals.",
            "published_requires_two_reviews",
        )
    if milestone.status not in (MilestoneStatus.SUBMITTED, MilestoneStatus.UNDER_REVIEW):
        raise ReviewError("Milestone is not under review.", "invalid_state")
    if milestone.current_round < 1:
        raise ReviewError("Milestone has no submitted round.", "invalid_state")
    if not milestone.onchain_milestone_pda or not milestone.project.onchain_project_pda:
        raise ReviewError("Milestone is not registered on-chain.", "milestone_not_registered")
    if not ReviewerAssignment.objects.filter(
        milestone=milestone, reviewer=reviewer, revoked_at__isnull=True
    ).exists():
        raise ReviewError("Reviewer is not assigned to this milestone.", "not_assigned")
    if Review.objects.filter(
        milestone=milestone, round=milestone.current_round, reviewer=reviewer
    ).exists():
        raise ReviewError("A verdict already exists for this round.", "verdict_exists")

    decision_value = ReviewDecision(decision)
    instruction = "verify_milestone" if decision_value == ReviewDecision.VERIFY else "reject_milestone"
    verification_address = pdas.verification_pda(
        milestone.onchain_milestone_pda, milestone.current_round, reviewer.wallet_address
    )
    intent = prepare_intent(
        intent="milestone.verdict",
        object_type="milestone",
        object_id=milestone.id,
        payload={
            "instruction": instruction,
            "program_id": settings.PROGRAM_ID,
            "signer": reviewer.wallet_address,
            "account": milestone.onchain_milestone_pda,
            "args": {"milestone_id_hex": milestone_id_hex(milestone)},
            "accounts": {
                "reviewer_wallet": reviewer.wallet_address,
                "registry": pdas.registry_pda(),
                "reviewer": pdas.reviewer_pda(reviewer.wallet_address),
                "project": milestone.project.onchain_project_pda,
                "milestone": milestone.onchain_milestone_pda,
                "verification": verification_address,
                "system_program": "11111111111111111111111111111111",
            },
            "internal": {
                "round": milestone.current_round,
                "reviewer_id": str(reviewer.id),
                "decision": decision_value,
                "comment": comment,
            },
        },
    )
    AuditLog.objects.create(
        actor=user,
        action="review.verdict_prepared",
        object_type="milestone",
        object_id=str(milestone.id),
        metadata={"round": milestone.current_round, "decision": decision_value},
    )
    return intent


@transaction.atomic
def deactivate_reviewer(admin, reviewer: Reviewer):
    if not admin.is_admin:
        raise ReviewError("Administrator role required.", "forbidden")
    reviewer = Reviewer.objects.select_for_update().get(pk=reviewer.pk)
    if not reviewer.active:
        raise ReviewError("Reviewer is already inactive.", "reviewer_inactive")
    if not reviewer.onchain_reviewer_pda:
        raise ReviewError("Reviewer is not registered on-chain.", "reviewer_not_registered")
    admin_wallet = _wallet_for(admin)
    if not admin_wallet:
        raise ReviewError("Admin has no linked wallet.", "wallet_missing")

    intent = prepare_intent(
        intent="reviewer.deactivate",
        object_type="reviewer",
        object_id=reviewer.id,
        payload={
            "instruction": "deactivate_reviewer",
            "program_id": settings.PROGRAM_ID,
            "signer": admin_wallet,
            "account": reviewer.onchain_reviewer_pda,
            "args": {"wallet": reviewer.wallet_address},
            "accounts": {
                "admin": admin_wallet,
                "registry": pdas.registry_pda(),
                "reviewer": reviewer.onchain_reviewer_pda,
            },
        },
    )
    AuditLog.objects.create(
        actor=admin,
        action="reviewer.deactivation_prepared",
        object_type="reviewer",
        object_id=str(reviewer.id),
    )
    return intent


@transaction.atomic
def file_dispute(user, review: Review, reason: str) -> Dispute:
    if len(reason.strip()) < 20:
        raise ReviewError("Dispute reason must be at least 20 characters.", "reason_too_short")
    if Dispute.objects.filter(review=review, filed_by=user, status=DisputeStatus.OPEN).exists():
        raise ReviewError("An open dispute already exists for this verdict.", "dispute_exists")
    dispute = Dispute.objects.create(review=review, filed_by=user, reason=reason.strip())
    AuditLog.objects.create(
        actor=user,
        action="dispute.filed",
        object_type="dispute",
        object_id=str(dispute.id),
        metadata={"review": str(review.id)},
    )
    return dispute


@transaction.atomic
def resolve_dispute(admin, dispute: Dispute, *, status: str, resolution: str) -> Dispute:
    if not admin.is_admin:
        raise ReviewError("Administrator role required.", "forbidden")
    if status not in (DisputeStatus.UPHELD, DisputeStatus.REJECTED):
        raise ReviewError("Dispute must be upheld or rejected.", "invalid_status")
    if len(resolution.strip()) < 5:
        raise ReviewError("Resolution must be at least 5 characters.", "resolution_too_short")
    dispute = Dispute.objects.select_for_update().get(pk=dispute.pk)
    if dispute.status != DisputeStatus.OPEN:
        raise ReviewError("Dispute is already resolved.", "dispute_resolved")
    dispute.status = status
    dispute.resolution = resolution.strip()
    dispute.resolved_by = admin
    dispute.resolved_at = timezone.now()
    dispute.save(update_fields=["status", "resolution", "resolved_by", "resolved_at", "updated_at"])
    AuditLog.objects.create(
        actor=admin,
        action="dispute.resolved",
        object_type="dispute",
        object_id=str(dispute.id),
        metadata={"status": status},
    )
    return dispute
