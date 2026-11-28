from __future__ import annotations

import hashlib
import json
import logging
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.chain import pdas
from apps.chain.services import prepare_intent
from apps.common.models import AuditLog
from apps.milestones.models import MilestoneStatus

from .models import (
    ApplicationStatus,
    FounderProfile,
    Project,
    ProjectApplication,
    ProjectApplicationDecision,
    ProjectCategory,
)

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    def __init__(self, message: str, code: str = "project_invalid"):
        super().__init__(message)
        self.code = code


def _unique_slug(name: str) -> str:
    base = slugify(name)[:120] or "project"
    candidate = base
    counter = 2
    while Project.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _wallet_for(user) -> str | None:
    wallet = user.wallets.filter(is_primary=True).first() or user.wallets.first()
    return wallet.address if wallet else None


@transaction.atomic
def create_project(user, data: dict) -> Project:
    category = None
    if data.get("category_slug"):
        category = ProjectCategory.objects.filter(slug=data["category_slug"]).first()
        if category is None:
            raise ProjectError("Unknown category.", "category_unknown")

    project = Project.objects.create(
        founder=user,
        name=data["name"],
        slug=_unique_slug(data["name"]),
        description=data["description"],
        website=data.get("website", ""),
        category=category,
    )
    AuditLog.objects.create(
        actor=user, action="project.created", object_type="project", object_id=str(project.id)
    )
    return project


@transaction.atomic
def update_founder_profile(user, data: dict) -> FounderProfile:
    profile, _ = FounderProfile.objects.update_or_create(
        user=user,
        defaults={
            "display_name": data["display_name"],
            "bio": data.get("bio", ""),
            "website": data.get("website", ""),
        },
    )
    return profile


@transaction.atomic
def submit_project(project: Project, user) -> Project:
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.founder_id != user.id:
        raise ProjectError("Only the founder can submit this project.", "forbidden")
    if project.application_status not in (ApplicationStatus.DRAFT, ApplicationStatus.REJECTED):
        raise ProjectError("Project is not in a submittable state.", "invalid_state")
    project.application_status = ApplicationStatus.SUBMITTED
    project.save(update_fields=["application_status", "updated_at"])
    ProjectApplication.objects.create(
        project=project, submitted_at=timezone.now(), decision=ProjectApplicationDecision.PENDING
    )
    AuditLog.objects.create(
        actor=user, action="project.submitted", object_type="project", object_id=str(project.id)
    )
    return project


def _metadata_document(project: Project) -> dict:
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "website": project.website if _safe_http_url(project.website) else "",
        "category": project.category.slug if project.category else None,
    }


def _metadata_hash(document: dict) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def decide_project(project: Project, admin, *, decision: str, notes: str = "") -> tuple[Project, object | None]:
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not admin.is_admin:
        raise ProjectError("Administrator role required.", "forbidden")
    if project.application_status not in (
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.UNDER_REVIEW,
    ):
        raise ProjectError("Project is not awaiting a decision.", "invalid_state")

    application = project.applications.order_by("-created_at").first()
    now = timezone.now()
    intent = None

    if decision == "reject":
        project.application_status = ApplicationStatus.REJECTED
        project.review_notes = notes
        project.save(update_fields=["application_status", "review_notes", "updated_at"])
        if application:
            application.decision = ProjectApplicationDecision.REJECTED
            application.reviewed_at = now
            application.reviewer = admin
            application.notes = notes
            application.save()
    elif decision == "approve":
        admin_wallet = _wallet_for(admin)
        founder_wallet = _wallet_for(project.founder)
        if not admin_wallet:
            raise ProjectError("Admin has no linked wallet.", "wallet_missing")
        if not founder_wallet:
            raise ProjectError("Founder has no linked wallet.", "wallet_missing")

        project.application_status = ApplicationStatus.APPROVED
        project.review_notes = notes
        project.approved_at = now
        project.approved_by = admin
        project.save(
            update_fields=[
                "application_status",
                "review_notes",
                "approved_at",
                "approved_by",
                "updated_at",
            ]
        )
        if application:
            application.decision = ProjectApplicationDecision.APPROVED
            application.reviewed_at = now
            application.reviewer = admin
            application.notes = notes
            application.save()

        metadata_uri = f"{settings.SIWS_URI.rstrip('/')}/projects/{project.slug}"
        if len(metadata_uri.encode("utf-8")) > 128:
            raise ProjectError("Public project URL exceeds the on-chain URI limit.", "uri_too_long")
        project_address = pdas.project_pda(project.id)
        intent = prepare_intent(
            intent="project.register",
            object_type="project",
            object_id=project.id,
            payload={
                "instruction": "register_project",
                "program_id": settings.PROGRAM_ID,
                "signer": admin_wallet,
                "account": project_address,
                "project_pda": project_address,
                "args": {
                    "project_id_hex": project.id.hex,
                    "metadata_hash_hex": _metadata_hash(_metadata_document(project)),
                    "metadata_uri": metadata_uri,
                    "founder": founder_wallet,
                },
                "founder": founder_wallet,
                "accounts": {
                    "admin": admin_wallet,
                    "registry": pdas.registry_pda(),
                    "project": project_address,
                    "system_program": "11111111111111111111111111111111",
                },
            },
        )
    else:
        raise ProjectError("Unknown decision.", "invalid_decision")

    AuditLog.objects.create(
        actor=admin,
        action=f"project.{decision}",
        object_type="project",
        object_id=str(project.id),
        metadata={"notes": notes},
    )
    return project, intent


def _safe_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value or "")
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def public_project_payload(project: Project, *, include_drafts: bool = False) -> dict:
    milestone_qs = project.milestones.all()
    if not include_drafts:
        milestone_qs = milestone_qs.exclude(status=MilestoneStatus.DRAFT)
    milestones = (
        milestone_qs
        .prefetch_related(
            "submissions__evidence",
            "reviews__reviewer",
            "reviews__disputes",
            "roadmap",
        )
        .order_by("deadline", "created_at")
    )
    milestone_payload = []
    for milestone in milestones:
        # Published verdicts require at least two approvals. R=1 is internal only.
        if milestone.required_approvals < 2:
            continue
        submission_payload = [
            {
                "round": submission.round,
                "evidence_uri": submission.evidence_uri
                if _safe_http_url(submission.evidence_uri)
                else "",
                "evidence_hash": bytes(submission.evidence_hash).hex(),
                "criteria_uri": submission.criteria_uri
                if _safe_http_url(submission.criteria_uri)
                else "",
                "criteria_hash": bytes(submission.criteria_hash).hex(),
                "evidence": [
                    {
                        "kind": item.kind,
                        "uri": item.uri,
                        "sha256": bytes(item.sha256).hex(),
                        "content_type": item.content_type,
                        "size_bytes": item.size_bytes,
                        "data_origin": item.data_origin,
                    }
                    for item in submission.evidence.all()
                    if _safe_http_url(item.uri)
                ],
                "submitted_at": submission.submitted_at,
                "data_origin": submission.data_origin,
                "chain": {
                    "signature": submission.chain_signature,
                    "slot": submission.chain_slot,
                },
            }
            for submission in milestone.submissions.all().order_by("round")
        ]
        review_payload = [
            {
                "id": review.id,
                "round": review.round,
                "decision": review.decision,
                "comment": review.comment,
                "reviewer_wallet": review.reviewer.wallet_address,
                "criteria_hash": bytes(review.criteria_hash).hex(),
                "created_at": review.created_at,
                "data_origin": review.data_origin,
                "chain": {"signature": review.chain_signature, "slot": review.chain_slot},
                "disputes": [
                    {
                        "id": dispute.id,
                        "status": dispute.status,
                        "reason": dispute.reason,
                        "resolution": dispute.resolution,
                        "created_at": dispute.created_at,
                        "resolved_at": dispute.resolved_at,
                    }
                    for dispute in review.disputes.all().order_by("created_at")
                ],
            }
            for review in milestone.reviews.all().order_by("round", "created_at")
        ]
        milestone_payload.append(
            {
                "id": milestone.id,
                "title": milestone.title,
                "description": milestone.description,
                "deadline": milestone.deadline,
                "status": milestone.status,
                "is_overdue": milestone.is_overdue,
                "current_round": milestone.current_round,
                "required_approvals": milestone.required_approvals,
                "roadmap": (
                    {
                        "id": milestone.roadmap_id,
                        "title": milestone.roadmap.title,
                        "order": milestone.roadmap.order,
                    }
                    if milestone.roadmap_id
                    else None
                ),
                "criteria": {
                    "template_id": str(milestone.criteria_template_id)
                    if milestone.criteria_template_id
                    else None,
                    "version": milestone.criteria_version,
                    "uri": milestone.criteria_uri
                    if _safe_http_url(milestone.criteria_uri)
                    else "",
                    "hash": bytes(milestone.criteria_hash).hex()
                    if milestone.criteria_hash
                    else "",
                },
                "chain": {
                    "pda": milestone.onchain_milestone_pda,
                    "signature": milestone.chain_signature,
                    "slot": milestone.chain_slot,
                    "status": milestone.chain_status,
                },
                "submissions": submission_payload,
                "reviews": review_payload,
            }
        )

    verified_count = sum(
        1 for item in milestone_payload if item["status"] == MilestoneStatus.VERIFIED
    )
    total_count = len(milestone_payload)
    progress = {
        "verified": verified_count,
        "total": total_count,
        "percentage": round((verified_count / total_count) * 100) if total_count else 0,
        "basis": (
            "Verified milestones divided by published milestones. "
            "No weighting, composite score or forecast."
        ),
    }
    roadmaps = [
        {
            "id": roadmap.id,
            "title": roadmap.title,
            "description": roadmap.description,
            "order": roadmap.order,
        }
        for roadmap in project.roadmaps.all().order_by("order", "created_at")
    ]

    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "website": project.website if _safe_http_url(project.website) else "",
        "category": project.category.name if project.category else None,
        "application_status": project.application_status,
        "lifecycle_status": project.lifecycle_status,
        "data_origin": project.data_origin,
        "token_mint": project.token_mint,
        "treasury_wallet": project.treasury_wallet,
        "treasury_chain": project.treasury_chain,
        "founder": {
            "id": project.founder_id,
            "display_name": project.founder.display_name,
        },
        "chain": {
            "pda": project.onchain_project_pda,
            "signature": project.chain_signature,
            "slot": project.chain_slot,
            "lifecycle_status": project.chain_lifecycle_status,
            "authority": project.chain_authority,
        },
        "progress": progress,
        "roadmaps": roadmaps,
        "milestones": milestone_payload,
        "notices": [
            "Information only. This page is not investment advice.",
            "Verification means the published criteria were met. It is not an endorsement or a safety rating.",
        ],
    }
