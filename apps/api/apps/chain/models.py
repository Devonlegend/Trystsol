import uuid

from django.db import models

from apps.common.models import DataOrigin, UUIDTimeStampedModel


class TransactionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    FAILED = "failed", "Failed"


class BlockchainTransaction(UUIDTimeStampedModel):
    """One row per submitted transaction, and the link to the off-chain object it changes."""

    signature = models.CharField(max_length=88)
    instruction_index = models.PositiveIntegerField(default=0)
    program_id = models.CharField(max_length=44)
    slot = models.BigIntegerField(null=True, blank=True)
    block_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=TransactionStatus.choices, default=TransactionStatus.PENDING
    )
    error = models.TextField(blank=True)
    intent = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )

    class Meta:
        db_table = "chain_transaction"
        constraints = [
            models.UniqueConstraint(
                fields=["signature", "instruction_index"], name="chain_transaction_signature_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[c[0] for c in TransactionStatus.choices]),
                name="chain_transaction_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(data_origin__in=[c[0] for c in DataOrigin.choices]),
                name="chain_transaction_data_origin_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["intent", "status"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.intent}:{self.signature}"


class ProcessedSignature(models.Model):
    signature = models.CharField(max_length=88)
    instruction_index = models.PositiveIntegerField(default=0)
    slot = models.BigIntegerField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chain_processed_signature"
        constraints = [
            models.UniqueConstraint(
                fields=["signature", "instruction_index"], name="processed_signature_unique"
            )
        ]

    def __str__(self) -> str:
        return self.signature


class IndexerCursor(models.Model):
    name = models.CharField(max_length=64, unique=True)
    last_signature = models.CharField(max_length=88, blank=True)
    last_slot = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chain_indexer_cursor"

    def __str__(self) -> str:
        return self.name


class SignedIntent(UUIDTimeStampedModel):
    """Server-prepared instruction payload that a wallet will sign.

    The server does not sign or send transactions in Phase 0. It prepares the payload,
    the client signs and sends, then posts the signature for confirmation.
    """

    intent = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.UUIDField()
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    data_origin = models.CharField(
        max_length=16, choices=DataOrigin.choices, default=DataOrigin.DEVNET
    )

    class Meta:
        db_table = "chain_signed_intent"
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def __str__(self) -> str:
        return f"{self.intent}:{self.id}"

