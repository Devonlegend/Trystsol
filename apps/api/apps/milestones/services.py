from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.chain import pdas
from apps.chain.services import prepare_intent
from apps.common.models import AuditLog
from apps.projects.models import ApplicationStatus, Project
from apps.reviews.models import Reviewer, ReviewerAssignment

from .models import Milestone, MilestoneStatus, Roadmap, VerificationCriteria

logger = logging.getLogger(__name__)


class MilestoneError(Exception):
    def __init__(self, message: str, code: str = "milestone_invalid"):
        super().__init__(message)
        self.code = code


def _wallet_for(user) -> str | None:
    wallet = user.wallets.filter(is_primary=True).first() or user.wallets.first()
    return wallet.address if wallet else None


def _require_registered_project(project: Project) -> str:
    if project.application_status != ApplicationStatus.APPROVED:
        raise MilestoneError("Project is not approved.", "project_not_approved")
    if not project.onchain_project_pda:
        raise MilestoneError(
            "Project is not registered on-chain yet; confirm the registration transaction first.",
            "project_not_registered",
        )
    return project.onchain_project_pda


@transaction.atomic
def create_milestone(project: Project, user, data: dict) -> tuple[Milestone, object]:
    if project.founder_id != user.id:
        raise MilestoneError("Only the founder can create milestones.", "forbidden")
    project_address = _require_registered_project(project)
    wallet = _wallet_for(user)
    if not wallet:
        raise MilestoneError("Founder has no linked wallet.", "wallet_missing")
    if project.chain_authority != wallet:
        raise MilestoneError(
            "The founder must accept project authority on-chain before creating milestones.",
            "authority_not_accepted",
        )
    criteria = VerificationCriteria.objects.filter(
        id=data.get("criteria_id"), active=True
    ).first()
    if criteria is None or not criteria.onchain_template_pda:
        raise MilestoneError("Criteria template is unknown or not published.", "criteria_invalid")

    roadmap = None
    if data.get("roadmap_id"):
        roadmap = project.roadmaps.filter(id=data["roadmap_id"]).first()
        if roadmap is None:
            raise MilestoneError("Roadmap does not belong to this project.", "roadmap_invalid")

    milestone = Milestone.objects.create(
        project=project,
        roadmap=roadmap,
        title=data["title"],
        description=data["description"],
        deadline=data["deadline"],
        required_approvals=data.get("required_approvals", 1),
        criteria_template=criteria,
        criteria_hash=bytes(criteria.criteria_hash),
        criteria_uri=criteria.criteria_uri,
        criteria_version=criteria.version,
        created_by=user,
    )
    milestone_address = pdas.milestone_pda(project_address, milestone.id)
    intent = prepare_intent(
        intent="milestone.create",
        object_type="milestone",
        object_id=milestone.id,
        payload={
            "instruction": "create_milestone",
            "program_id": settings.PROGRAM_ID,
            "signer": wallet,
            "account": milestone_address,
            "milestone_pda": milestone_address,
            "args": {
                "milestone_id_hex": milestone.id.hex,
                "criteria_template_id_hex": criteria.id.hex,
            },
            "accounts": {
                "authority": wallet,
                "project": project_address,
                "milestone": milestone_address,
                "criteria_template": criteria.onchain_template_pda,
                "system_program": "11111111111111111111111111111111",
            },
            "internal": {"milestone_id_hex": milestone.id.hex},
        },
    )
    AuditLog.objects.create(
        actor=user, action="milestone.created", object_type="milestone", object_id=str(milestone.id)
    )
    return milestone, intent


@transaction.atomic
def assign_reviewers(admin, milestone: Milestone, *, reviewer_ids, required_approvals: int):
    if not admin.is_admin:
        raise MilestoneError("Administrator role required.", "forbidden")
    milestone = Milestone.objects.select_for_update().select_related("project").get(pk=milestone.pk)
    project_address = _require_registered_project(milestone.project)
    if not milestone.onchain_milestone_pda:
        raise MilestoneError("Milestone is not registered on-chain.", "milestone_not_registered")
    if milestone.status not in (MilestoneStatus.DRAFT, MilestoneStatus.REJECTED):
        raise MilestoneError("Milestone is not open for reviewer assignment.", "invalid_state")

    reviewers = list(Reviewer.objects.filter(id__in=reviewer_ids, active=True))
    if len(reviewers) != len(reviewer_ids) or len(set(reviewer_ids)) != len(reviewer_ids):
        raise MilestoneError("One or more reviewers are unknown or inactive.", "reviewer_invalid")
    if required_approvals < 2:
        raise MilestoneError(
            "Published verdicts require at least two required approvals.",
            "published_requires_two_reviews",
        )
    if required_approvals > len(reviewers):
        raise MilestoneError("required_approvals cannot exceed the reviewer count.", "invalid_approvals")
    if milestone.project.founder_id in [reviewer.user_id for reviewer in reviewers]:
        raise MilestoneError("The project founder cannot review their own milestone.", "self_review")
    admin_wallet = _wallet_for(admin)
    if not admin_wallet:
        raise MilestoneError("Admin has no linked wallet.", "wallet_missing")

    wallets = [reviewer.wallet_address for reviewer in reviewers]
    intent = prepare_intent(
        intent="milestone.assign",
        object_type="milestone",
        object_id=milestone.id,
        payload={
            "instruction": "assign_reviewers",
            "program_id": settings.PROGRAM_ID,
            "signer": admin_wallet,
            "account": milestone.onchain_milestone_pda,
            "args": {
                "milestone_id_hex": milestone_id_hex(milestone),
                "reviewers": wallets,
                "required_approvals": required_approvals,
            },
            "accounts": {
                "admin": admin_wallet,
                "registry": pdas.registry_pda(),
                "project": project_address,
                "milestone": milestone.onchain_milestone_pda,
                "reviewer_accounts": [pdas.reviewer_pda(wallet) for wallet in wallets],
            },
            "internal": {
                "reviewer_ids": [str(reviewer.id) for reviewer in reviewers],
                "assigned_by": str(admin.id),
            },
        },
    )
    return intent


def milestone_id_hex(milestone: Milestone) -> str:
    """The on-chain milestone id is the database UUID (16 bytes).

    Using the same identifier avoids a second mapping table and keeps PDA derivation
    reproducible from either side.
    """
    return milestone.id.hex


@transaction.atomic
def submit_milestone(milestone: Milestone, user, data: dict):
    milestone = Milestone.objects.select_for_update().select_related("project").get(pk=milestone.pk)
    if milestone.project.founder_id != user.id:
        raise MilestoneError("Only the founder can submit this milestone.", "forbidden")
    project_address = _require_registered_project(milestone.project)
    if not milestone.onchain_milestone_pda:
        raise MilestoneError("Milestone is not registered on-chain.", "milestone_not_registered")
    if milestone.status not in (MilestoneStatus.DRAFT, MilestoneStatus.REJECTED):
        raise MilestoneError("Milestone is not open for submission.", "invalid_state")
    if milestone.required_approvals < 1:
        raise MilestoneError("Assign reviewers before submitting.", "reviewers_not_assigned")
    if not milestone.reviewer_assignments.filter(revoked_at__isnull=True).exists():
        raise MilestoneError("Assign reviewers before submitting.", "reviewers_not_assigned")

    wallet = _wallet_for(user)
    if not wallet:
        raise MilestoneError("Founder has no linked wallet.", "wallet_missing")
    if not milestone.criteria_hash or not milestone.criteria_uri:
        raise MilestoneError("Milestone has no fixed criteria template.", "criteria_missing")
    milestone_id = milestone_id_hex(milestone)
    if not milestone_id:
        raise MilestoneError("Milestone id is missing from its creation intent.", "milestone_id_missing")

    round_number = milestone.current_round + 1
    if round_number > 65535:
        raise MilestoneError("Round limit reached.", "round_overflow")

    primary = data["evidence"][0]
    intent = prepare_intent(
        intent="milestone.submit",
        object_type="milestone",
        object_id=milestone.id,
        payload={
            "instruction": "submit_milestone",
            "program_id": settings.PROGRAM_ID,
            "signer": wallet,
            "account": milestone.onchain_milestone_pda,
            "args": {
                "milestone_id_hex": milestone_id,
                "evidence_hash_hex": primary["sha256"],
                "evidence_uri": primary["uri"],
            },
            "accounts": {
                "authority": wallet,
                "project": project_address,
                "milestone": milestone.onchain_milestone_pda,
            },
            "internal": {
                "round": round_number,
                "submitted_by": str(user.id),
                "evidence": data["evidence"],
            },
        },
    )
    AuditLog.objects.create(
        actor=user,
        action="milestone.submission_prepared",
        object_type="milestone",
        object_id=str(milestone.id),
        metadata={"round": round_number},
    )
    return intent


@transaction.atomic
def create_roadmap(project, user, data: dict) -> Roadmap:
    if project.founder_id != user.id:
        raise MilestoneError("Only the founder can create roadmaps.", "forbidden")
    if project.application_status != ApplicationStatus.APPROVED:
        raise MilestoneError("Project is not approved.", "project_not_approved")
    roadmap = Roadmap.objects.create(
        project=project,
        title=data["title"],
        description=data.get("description", ""),
        order=data.get("order", 0),
        created_by=user,
    )
    AuditLog.objects.create(
        actor=user,
        action="roadmap.created",
        object_type="roadmap",
        object_id=str(roadmap.id),
    )
    return roadmap


@transaction.atomic
def update_roadmap(roadmap: Roadmap, user, data: dict) -> Roadmap:
    roadmap = Roadmap.objects.select_for_update().select_related("project").get(pk=roadmap.pk)
    if roadmap.project.founder_id != user.id:
        raise MilestoneError("Only the founder can edit roadmaps.", "forbidden")
    for field in ("title", "description", "order"):
        if field in data:
            setattr(roadmap, field, data[field])
    roadmap.save()
    AuditLog.objects.create(
        actor=user,
        action="roadmap.updated",
        object_type="roadmap",
        object_id=str(roadmap.id),
    )
    return roadmap


@transaction.atomic
def publish_criteria(admin, data: dict):
    if not admin.is_admin:
        raise MilestoneError("Administrator role required.", "forbidden")
    wallet = _wallet_for(admin)
    if not wallet:
        raise MilestoneError("Admin has no linked wallet.", "wallet_missing")
    criteria = VerificationCriteria.objects.create(
        version=data["version"],
        criteria_hash=bytes.fromhex(data["criteria_hash"]),
        criteria_uri=data["criteria_uri"],
        published_by=admin,
        published_at=timezone.now(),
        active=True,
    )
    criteria_address = pdas.criteria_pda(criteria.id)
    intent = prepare_intent(
        intent="criteria.publish",
        object_type="criteria",
        object_id=criteria.id,
        payload={
            "instruction": "publish_criteria_template",
            "program_id": settings.PROGRAM_ID,
            "signer": wallet,
            "account": criteria_address,
            "criteria_pda": criteria_address,
            "args": {
                "template_id_hex": criteria.id.hex,
                "version": criteria.version,
                "criteria_hash_hex": data["criteria_hash"],
                "criteria_uri": criteria.criteria_uri,
            },
            "accounts": {
                "admin": wallet,
                "registry": pdas.registry_pda(),
                "criteria_template": criteria_address,
                "system_program": "11111111111111111111111111111111",
            },
        },
    )
    AuditLog.objects.create(
        actor=admin,
        action="criteria.published",
        object_type="criteria",
        object_id=str(criteria.id),
        metadata={"version": criteria.version},
    )
    return criteria, intent


@transaction.atomic
def expire_round(admin, milestone: Milestone):
    if not admin.is_admin:
        raise MilestoneError("Administrator role required.", "forbidden")
    milestone = Milestone.objects.select_for_update().select_related("project").get(pk=milestone.pk)
    if milestone.status not in (MilestoneStatus.SUBMITTED, MilestoneStatus.UNDER_REVIEW):
        raise MilestoneError("Only a submitted or under-review round can be expired.", "invalid_state")
    if not milestone.onchain_milestone_pda or not milestone.project.onchain_project_pda:
        raise MilestoneError("Milestone is not registered on-chain.", "milestone_not_registered")
    wallet = _wallet_for(admin)
    if not wallet:
        raise MilestoneError("Admin has no linked wallet.", "wallet_missing")
    intent = prepare_intent(
        intent="milestone.expire",
        object_type="milestone",
        object_id=milestone.id,
        payload={
            "instruction": "expire_round",
            "program_id": settings.PROGRAM_ID,
            "signer": wallet,
            "account": milestone.onchain_milestone_pda,
            "args": {"milestone_id_hex": milestone_id_hex(milestone)},
            "accounts": {
                "admin": wallet,
                "registry": pdas.registry_pda(),
                "project": milestone.project.onchain_project_pda,
                "milestone": milestone.onchain_milestone_pda,
            },
        },
    )
    AuditLog.objects.create(
        actor=admin,
        action="milestone.round_expired",
        object_type="milestone",
        object_id=str(milestone.id),
        metadata={"round": milestone.current_round},
    )
    return intent
