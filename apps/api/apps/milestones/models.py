from django.conf import settings
from django.db import models

from apps.common.models import DataOrigin, UUIDTimeStampedModel


class VerificationCriteria(UUIDTimeStampedModel):
    """Admin-published, versioned criteria template. The content is immutable."""

    version = models.PositiveIntegerField()
    criteria_hash = models.BinaryField(max_length=32)
    criteria_uri = models.CharField(max_length=128)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="published_criteria"
    )
    published_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    onchain_template_pda = models.CharField(max_length=44, blank=True)
    chain_signature = models.CharField(max_length=88, blank=True)

    class Meta:
        db_table = "milestones_verification_criteria"
        indexes = [models.Index(fields=["active", "version"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(version__gte=1), name="criteria_version_positive"),
        ]

    def __str__(self) -> str:
        return f"criteria-v{self.version}"


class Roadmap(UUIDTimeStampedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="roadmaps"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_roadmaps"
    )

    class Meta:
        db_table = "milestones_roadmap"
        ordering = ["order", "created_at"]
        indexes = [models.Index(fields=["project", "order"])]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.title}"


class MilestoneStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class Milestone(UUIDTimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="milestones")
    roadmap = models.ForeignKey(
        Roadmap,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="roadmap_milestones",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    deadline = models.DateField()
    status = models.CharField(
        max_length=20, choices=MilestoneStatus.choices, default=MilestoneStatus.DRAFT
    )
    current_round = models.PositiveIntegerField(default=0)
    required_approvals = models.PositiveSmallIntegerField(default=1)
    criteria_template = models.ForeignKey(
        VerificationCriteria,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="milestones",
    )
    criteria_hash = models.BinaryField(max_length=32, null=True, blank=True)
    criteria_uri = models.CharField(max_length=128, blank=True)
    criteria_version = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_milestones"
    )

    onchain_milestone_pda = models.CharField(max_length=44, blank=True)
    chain_signature = models.CharField(max_length=88, blank=True)
    chain_slot = models.BigIntegerField(null=True, blank=True)
    chain_status = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "milestones_milestone"
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["deadline"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=[c[0] for c in MilestoneStatus.choices]),
                name="milestone_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(required_approvals__gte=1),
                name="milestone_required_approvals_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(current_round__gte=0),
                name="milestone_current_round_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.title}"

    @property
    def is_overdue(self) -> bool:
        """Overdue is derived, never stored (brief section 7)."""
        import datetime as dt

        if self.status in (MilestoneStatus.VERIFIED, MilestoneStatus.REJECTED):
            return False
        return self.deadline < dt.date.today()


class MilestoneSubmission(UUIDTimeStampedModel):
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="submissions")
    round = models.PositiveIntegerField()
    evidence_hash = models.BinaryField(max_length=32)
    evidence_uri = models.CharField(max_length=128)
    criteria_hash = models.BinaryField(max_length=32)
    criteria_uri = models.CharField(max_length=128)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="milestone_submissions"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )

    chain_signature = models.CharField(max_length=88, blank=True)
    chain_slot = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "milestones_submission"
        constraints = [
            models.UniqueConstraint(fields=["milestone", "round"], name="milestone_submission_round_unique"),
            models.CheckConstraint(condition=models.Q(round__gte=1), name="milestone_submission_round_positive"),
            models.CheckConstraint(
                condition=models.Q(data_origin__in=[c[0] for c in DataOrigin.choices]),
                name="milestone_submission_data_origin_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.milestone_id}:round-{self.round}"
