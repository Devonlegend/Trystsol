from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chain.services import serialize_intent
from apps.milestones.models import Milestone
from apps.milestones.serializers import ReviewerVerdictSerializer
from apps.reviews.models import Dispute, Review, Reviewer

from . import services
from .serializers import (
    DisputeCreateSerializer,
    DisputeResolveSerializer,
    ReviewerCreateSerializer,
)


class ReviewerRegistryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        reviewers = Reviewer.objects.select_related("user").order_by("-created_at")
        return Response(
            {
                "results": [
                    {
                        "id": reviewer.id,
                        "wallet_address": reviewer.wallet_address,
                        "active": reviewer.active,
                        "display_name": reviewer.user.display_name,
                        "onchain_pda": reviewer.onchain_reviewer_pda,
                        "chain_signature": reviewer.chain_signature,
                    }
                    for reviewer in reviewers
                ]
            }
        )

    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ReviewerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reviewer, intent = services.register_reviewer(
                request.user, serializer.validated_data["wallet_address"]
            )
        except services.ReviewError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "reviewer": {
                    "id": reviewer.id,
                    "wallet_address": reviewer.wallet_address,
                    "active": reviewer.active,
                },
                "intent": serialize_intent(intent),
            },
            status=status.HTTP_201_CREATED,
        )


class ReviewerDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reviewer_id):
        reviewer = get_object_or_404(Reviewer, pk=reviewer_id)
        try:
            intent = services.deactivate_reviewer(request.user, reviewer)
        except services.ReviewError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"intent": serialize_intent(intent)}, status=status.HTTP_201_CREATED)


class AdminDisputeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = (
            Dispute.objects.select_related(
                "review__milestone__project", "filed_by", "resolved_by"
            )
            .order_by("-created_at")
        )
        requested_status = request.query_params.get("status")
        if requested_status:
            queryset = queryset.filter(status=requested_status)
        return Response(
            {
                "results": [
                    {
                        "id": dispute.id,
                        "status": dispute.status,
                        "reason": dispute.reason,
                        "resolution": dispute.resolution,
                        "created_at": dispute.created_at,
                        "resolved_at": dispute.resolved_at,
                        "filed_by": dispute.filed_by.display_name
                        or str(dispute.filed_by_id),
                        "project": {
                            "id": dispute.review.milestone.project_id,
                            "name": dispute.review.milestone.project.name,
                            "slug": dispute.review.milestone.project.slug,
                        },
                        "milestone": {
                            "id": dispute.review.milestone_id,
                            "title": dispute.review.milestone.title,
                        },
                        "review_id": dispute.review_id,
                    }
                    for dispute in queryset[:200]
                ]
            }
        )


class MilestoneReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, milestone_id):
        serializer = ReviewerVerdictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = get_object_or_404(Milestone, pk=milestone_id)
        try:
            intent = services.submit_verdict(
                request.user,
                milestone,
                decision=serializer.validated_data["decision"],
                comment=serializer.validated_data.get("comment", ""),
            )
        except services.ReviewError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"intent": serialize_intent(intent)}, status=status.HTTP_201_CREATED)


class ReviewerAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            reviewer = Reviewer.objects.get(user=request.user, active=True)
        except Reviewer.DoesNotExist:
            return Response({"results": []})
        assignments = (
            reviewer.assignments.filter(revoked_at__isnull=True)
            .select_related("milestone__project")
            .order_by("milestone__deadline")
        )
        return Response(
            {
                "results": [
                    {
                        "milestone_id": assignment.milestone_id,
                        "title": assignment.milestone.title,
                        "status": assignment.milestone.status,
                        "round": assignment.milestone.current_round,
                        "required_approvals": assignment.milestone.required_approvals,
                        "deadline": assignment.milestone.deadline,
                        "project": {
                            "id": assignment.milestone.project_id,
                            "name": assignment.milestone.project.name,
                            "slug": assignment.milestone.project.slug,
                        },
                    }
                    for assignment in assignments
                ]
            }
        )


class FileDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, review_id):
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = get_object_or_404(Review.objects.select_related("milestone"), pk=review_id)
        try:
            dispute = services.file_dispute(
                request.user, review, serializer.validated_data["reason"]
            )
        except services.ReviewError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "id": dispute.id,
                "review_id": dispute.review_id,
                "status": dispute.status,
                "reason": dispute.reason,
                "created_at": dispute.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class ResolveDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, dispute_id):
        serializer = DisputeResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispute = get_object_or_404(Dispute, pk=dispute_id)
        try:
            dispute = services.resolve_dispute(
                request.user,
                dispute,
                status=serializer.validated_data["status"],
                resolution=serializer.validated_data["resolution"],
            )
        except services.ReviewError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "id": dispute.id,
                "status": dispute.status,
                "resolution": dispute.resolution,
                "resolved_at": dispute.resolved_at,
            }
        )
