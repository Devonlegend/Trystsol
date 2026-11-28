from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import DataOrigin, UUIDTimeStampedModel

MAX_EVIDENCE_BYTES = 25 * 1024 * 1024


class EvidenceKind(models.TextChoices):
    REPO = "repo", "Repository"
    DOCUMENT = "document", "Document"
    URL = "url", "URL"
    FILE = "file", "File"


class Evidence(UUIDTimeStampedModel):
    submission = models.ForeignKey(
        "milestones.MilestoneSubmission", on_delete=models.CASCADE, related_name="evidence"
    )
    kind = models.CharField(max_length=16, choices=EvidenceKind.choices)
    uri = models.CharField(max_length=2048)
    sha256 = models.BinaryField(max_length=32)
    content_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )

    class Meta:
        db_table = "evidence_evidence"
        indexes = [models.Index(fields=["submission"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=[c[0] for c in EvidenceKind.choices]),
                name="evidence_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(data_origin__in=[c[0] for c in DataOrigin.choices]),
                name="evidence_data_origin_valid",
            ),
        ]

    def clean(self):
        if self.size_bytes and self.size_bytes > MAX_EVIDENCE_BYTES:
            raise ValidationError({"size_bytes": "Evidence exceeds the 25 MiB limit."})

    def __str__(self) -> str:
        return f"{self.kind}:{self.uri}"
