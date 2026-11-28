import uuid

from django.db import models


class DataOrigin(models.TextChoices):
    SIMULATED = "simulated", "Simulated"
    DEVNET = "devnet", "Devnet"
    MAINNET = "mainnet", "Mainnet"


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDTimeStampedModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Append-only audit trail. There is no update or delete path."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "common_audit_log"
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("AuditLog is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog is append-only.")

    def __str__(self) -> str:
        return f"{self.action}:{self.object_type}:{self.object_id}"
