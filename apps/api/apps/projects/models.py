from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import DataOrigin, UUIDTimeStampedModel

SLUG_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    message="Slug must be lowercase letters, digits and single hyphens.",
)


class ApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class LifecycleStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    SUSPENDED = "suspended", "Suspended"


class FounderProfile(UUIDTimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="founder_profile"
    )
    display_name = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)

    class Meta:
        db_table = "projects_founder_profile"

    def __str__(self) -> str:
        return self.display_name


class ProjectCategory(UUIDTimeStampedModel):
    slug = models.SlugField(max_length=64, unique=True, validators=[SLUG_VALIDATOR])
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "projects_category"
        verbose_name_plural = "project categories"

    def __str__(self) -> str:
        return self.name


class Project(UUIDTimeStampedModel):
    founder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, validators=[SLUG_VALIDATOR])
    description = models.TextField()
    website = models.URLField(blank=True)
    category = models.ForeignKey(
        ProjectCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects"
    )

    application_status = models.CharField(
        max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.DRAFT
    )
    lifecycle_status = models.CharField(
        max_length=20, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE
    )
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )
    # Mainnet token mint for the decision page. Jupiter data is Mainnet-only.
    token_mint = models.CharField(max_length=44, blank=True)
    # Declared treasury wallet. Ownership is not asserted by this field.
    treasury_wallet = models.CharField(max_length=44, blank=True)
    treasury_chain = models.CharField(
        max_length=16,
        choices=[("devnet", "Devnet"), ("mainnet", "Mainnet")],
        default="devnet",
    )

    review_notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_projects",
    )

    # Written only by the chain confirmation / indexer paths.
    onchain_project_pda = models.CharField(max_length=44, blank=True)
    chain_authority = models.CharField(max_length=44, blank=True)
    chain_signature = models.CharField(max_length=88, blank=True)
    chain_slot = models.BigIntegerField(null=True, blank=True)
    chain_lifecycle_status = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "projects_project"
        indexes = [
            models.Index(fields=["application_status"]),
            models.Index(fields=["founder"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(application_status__in=[c[0] for c in ApplicationStatus.choices]),
                name="project_application_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(lifecycle_status__in=[c[0] for c in LifecycleStatus.choices]),
                name="project_lifecycle_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(data_origin__in=[c[0] for c in DataOrigin.choices]),
                name="project_data_origin_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ProjectApplicationDecision(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ProjectApplication(UUIDTimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="applications")
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_applications",
    )
    decision = models.CharField(
        max_length=16, choices=ProjectApplicationDecision.choices, default=ProjectApplicationDecision.PENDING
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "projects_application"
        indexes = [models.Index(fields=["project", "decision"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(decision__in=[c[0] for c in ProjectApplicationDecision.choices]),
                name="project_application_decision_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.decision}"
