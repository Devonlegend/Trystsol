import datetime as dt
import hashlib
import hmac
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.models import AuditLog
from apps.milestones.models import Milestone, MilestoneStatus
from apps.projects.models import Project

from .models import (
    BlockchainTransaction,
    IndexerCursor,
    ProcessedSignature,
    SignedIntent,
    TransactionStatus,
)
from .serializers import ConfirmIntentRequest, IndexerIngestRequest
from .services import IntentError, confirm_intent, serialize_intent

logger = logging.getLogger(__name__)


class ConfirmIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, intent_id):
        serializer = ConfirmIntentRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = confirm_intent(
                intent_id=intent_id,
                signature=serializer.validated_data["signature"],
                user=request.user,
            )
        except IntentError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "id": str(record.id),
                "signature": record.signature,
                "slot": record.slot,
                "status": record.status,
                "intent": record.intent,
                "object_type": record.object_type,
                "object_id": str(record.object_id) if record.object_id else None,
            }
        )


class IndexerIngestView(APIView):
    """Shared-secret endpoint used by the indexer. No user session is involved."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        provided = request.META.get("HTTP_X_INDEXER_SECRET", "")
        expected = settings.INDEXER_SHARED_SECRET
        if not expected or not hmac.compare_digest(provided, expected):
            return Response(
                {"error": {"code": "forbidden", "message": "Invalid indexer secret."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = IndexerIngestRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            duplicate = ProcessedSignature.objects.filter(
                signature=data["signature"], instruction_index=0
            ).exists()
            if duplicate:
                return Response({"status": "duplicate"})

            block_dt = (
                dt.datetime.fromtimestamp(data["block_time"], tz=dt.timezone.utc)
                if data.get("block_time")
                else None
            )
            BlockchainTransaction.objects.get_or_create(
                signature=data["signature"],
                instruction_index=0,
                defaults={
                    "program_id": settings.PROGRAM_ID,
                    "slot": data["slot"],
                    "block_time": block_dt,
                    "status": TransactionStatus.CONFIRMED,
                    "intent": "indexer.snapshot",
                    "processed_at": timezone.now(),
                },
            )

            updated = {"projects": 0, "milestones": 0}
            for snapshot in data["projects"]:
                count = Project.objects.filter(onchain_project_pda=snapshot["pda"]).update(
                    chain_lifecycle_status=snapshot["lifecycle_status"],
                    chain_signature=data["signature"],
                    chain_slot=data["slot"],
                )
                updated["projects"] += count

            for snapshot in data["milestones"]:
                values = {
                    "chain_status": snapshot["status"],
                    "chain_signature": data["signature"],
                    "chain_slot": data["slot"],
                    "current_round": snapshot["round"],
                }
                if snapshot["status"] in MilestoneStatus.values:
                    values["status"] = snapshot["status"]
                count = Milestone.objects.filter(onchain_milestone_pda=snapshot["pda"]).update(
                    **values
                )
                updated["milestones"] += count

            ProcessedSignature.objects.create(
                signature=data["signature"], instruction_index=0, slot=data["slot"]
            )
            IndexerCursor.objects.update_or_create(
                name=data.get("cursor_name") or "main",
                defaults={
                    "last_signature": data["signature"],
                    "last_slot": data["slot"],
                },
            )
            AuditLog.objects.create(
                action="indexer.snapshot",
                object_type="chain",
                object_id=data["signature"],
                metadata={"slot": data["slot"], "updated": updated},
            )

        return Response({"status": "ok", "updated": updated})


class IndexerStateView(APIView):
    """Cursor read endpoint for the indexer worker."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        provided = request.META.get("HTTP_X_INDEXER_SECRET", "")
        expected = settings.INDEXER_SHARED_SECRET
        if not expected or not hmac.compare_digest(provided, expected):
            return Response(
                {"error": {"code": "forbidden", "message": "Invalid indexer secret."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        name = request.query_params.get("name", "main")
        cursor = IndexerCursor.objects.filter(name=name).first()
        return Response(
            {
                "name": name,
                "last_signature": cursor.last_signature if cursor else "",
                "last_slot": cursor.last_slot if cursor else None,
            }
        )


class PendingIntentsView(APIView):
    """Recover un-signed server intents after a page reload or wallet hiccup."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = SignedIntent.objects.filter(
            consumed_at__isnull=True, expires_at__gt=timezone.now()
        ).order_by("-created_at")
        object_type = request.query_params.get("object_type")
        object_id = request.query_params.get("object_id")
        if object_type:
            queryset = queryset.filter(object_type=object_type)
        if object_id:
            try:
                queryset = queryset.filter(object_id=uuid.UUID(object_id))
            except ValueError:
                return Response(
                    {"error": {"code": "validation_error", "message": "Invalid object_id."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response({"results": [serialize_intent(intent) for intent in queryset[:20]]})
