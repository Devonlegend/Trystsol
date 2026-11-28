from __future__ import annotations

from django.utils import timezone

from apps.milestones.models import Milestone, MilestoneStatus
from apps.projects.models import ApplicationStatus, Project


def builder_passport(user) -> dict:
    """Public history derived only from verified milestone records. No score."""
    projects = Project.objects.filter(
        founder=user, application_status=ApplicationStatus.APPROVED
    ).order_by("name")
    milestones = (
        Milestone.objects.filter(
            project__in=projects,
            status=MilestoneStatus.VERIFIED,
            required_approvals__gte=2,
        )
        .select_related("project")
        .prefetch_related("reviews")
        .order_by("-updated_at")
    )
    entries = []
    project_ids = set()
    for milestone in milestones:
        project_ids.add(milestone.project_id)
        reviews = list(milestone.reviews.all())
        verified_at = max((review.created_at for review in reviews), default=milestone.updated_at)
        entries.append(
            {
                "project": {
                    "id": milestone.project_id,
                    "name": milestone.project.name,
                    "slug": milestone.project.slug,
                },
                "milestone": {
                    "id": milestone.id,
                    "title": milestone.title,
                    "round": milestone.current_round,
                    "verified_at": verified_at,
                    "chain": {
                        "pda": milestone.onchain_milestone_pda,
                        "signature": milestone.chain_signature,
                        "slot": milestone.chain_slot,
                    },
                },
                "reviews": [
                    {
                        "decision": review.decision,
                        "reviewer_wallet": review.reviewer.wallet_address,
                        "created_at": review.created_at,
                        "chain_signature": review.chain_signature,
                    }
                    for review in reviews
                ],
            }
        )

    return {
        "builder": {
            "id": user.id,
            "display_name": user.display_name or "Unnamed builder",
        },
        "verified_milestones": len(entries),
        "projects_with_verified_milestones": len(project_ids),
        "entries": entries,
        "generated_at": timezone.now(),
        "notice": (
            "Derived only from verified milestones with at least two approvals. "
            "No score, rating or prediction is calculated."
        ),
    }
