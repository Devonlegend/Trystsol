from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import DataOrigin, UUIDTimeStampedModel


class Reviewer(UUIDTimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviewer_profile"
    )
    wallet_address = models.CharField(max_length=44, unique=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointed_reviewers"
    )
    approved_at = models.DateTimeField()
    active = models.BooleanField(default=True)

    onchain_reviewer_pda = models.CharField(max_length=44, blank=True)
    chain_signature = models.CharField(max_length=88, blank=True)

    class Meta:
        db_table = "reviews_reviewer"
        indexes = [models.Index(fields=["active"])]

    def __str__(self) -> str:
        return self.wallet_address


class ReviewerAssignment(UUIDTimeStampedModel):
    milestone = models.ForeignKey(
        "milestones.Milestone", on_delete=models.CASCADE, related_name="reviewer_assignments"
    )
    reviewer = models.ForeignKey(Reviewer, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviewer_assignments_made"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    chain_signature = models.CharField(max_length=88, blank=True)

    class Meta:
        db_table = "reviews_assignment"
        constraints = [
            models.UniqueConstraint(fields=["milestone", "reviewer"], name="reviewer_assignment_unique"),
        ]
        indexes = [models.Index(fields=["milestone"])]

    def __str__(self) -> str:
        return f"{self.milestone_id}:{self.reviewer_id}"


class DisputeStatus(models.TextChoices):
    OPEN = "open", "Open"
    UPHELD = "upheld", "Upheld"
    REJECTED = "rejected", "Rejected"


class Dispute(UUIDTimeStampedModel):
    """A challenge to a published verdict. The reason is append-only."""

    review = models.ForeignKey("Review", on_delete=models.PROTECT, related_name="disputes")
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="filed_disputes"
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=16, choices=DisputeStatus.choices, default=DisputeStatus.OPEN
    )
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_disputes",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reviews_dispute"
        indexes = [
            models.Index(fields=["review", "status"]),
            models.Index(fields=["filed_by"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=[c[0] for c in DisputeStatus.choices]),
                name="dispute_status_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.review_id}:{self.status}"


class ReviewDecision(models.TextChoices):
    VERIFY = "verify", "Verify"
    REJECT = "reject", "Reject"


class Review(UUIDTimeStampedModel):
    """Append-only review record. No update or delete path exists."""

    milestone = models.ForeignKey(
        "milestones.Milestone", on_delete=models.PROTECT, related_name="reviews"
    )
    submission = models.ForeignKey(
        "milestones.MilestoneSubmission", on_delete=models.PROTECT, related_name="reviews"
    )
    round = models.PositiveIntegerField()
    reviewer = models.ForeignKey(Reviewer, on_delete=models.PROTECT, related_name="reviews")
    decision = models.CharField(max_length=8, choices=ReviewDecision.choices)
    comment = models.TextField(blank=True)
    criteria_hash = models.BinaryField(max_length=32)
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )

    chain_signature = models.CharField(max_length=88, blank=True)
    chain_slot = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "reviews_review"
        constraints = [
            models.UniqueConstraint(
                fields=["milestone", "round", "reviewer"], name="review_one_per_reviewer_per_round"
            ),
            models.CheckConstraint(
                condition=models.Q(decision__in=[c[0] for c in ReviewDecision.choices]),
                name="review_decision_valid",
            ),
            models.CheckConstraint(condition=models.Q(round__gte=1), name="review_round_positive"),
            models.CheckConstraint(
                condition=models.Q(data_origin__in=[c[0] for c in DataOrigin.choices]),
                name="review_data_origin_valid",
            ),
        ]
        indexes = [models.Index(fields=["milestone", "round"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Reviews are append-only and cannot be modified.")
        if self.submission.milestone_id != self.milestone_id:
            raise ValidationError("Review submission does not belong to the milestone.")
        if self.submission.round != self.round:
            raise ValidationError("Review round does not match the submission round.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Reviews are append-only and cannot be deleted.")

    def __str__(self) -> str:
        return f"{self.milestone_id}:r{self.round}:{self.decision}"
