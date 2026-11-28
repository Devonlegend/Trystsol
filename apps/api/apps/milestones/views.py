from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chain.services import serialize_intent
from apps.projects.models import Project

from . import services
from .models import Milestone, Roadmap, VerificationCriteria
from .serializers import (
    AssignReviewersSerializer,
    CriteriaCreateSerializer,
    MilestoneCreateSerializer,
    RoadmapCreateSerializer,
    RoadmapUpdateSerializer,
    SubmitMilestoneSerializer,
)


def _milestone_summary(milestone: Milestone) -> dict:
    return {
        "id": milestone.id,
        "project_id": milestone.project_id,
        "title": milestone.title,
        "description": milestone.description,
        "deadline": milestone.deadline,
        "status": milestone.status,
        "is_overdue": milestone.is_overdue,
        "current_round": milestone.current_round,
        "required_approvals": milestone.required_approvals,
        "chain": {
            "pda": milestone.onchain_milestone_pda,
            "signature": milestone.chain_signature,
            "slot": milestone.chain_slot,
            "status": milestone.chain_status,
        },
    }


class MilestoneCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        serializer = MilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=project_id)
        try:
            milestone, intent = services.create_milestone(
                project, request.user, serializer.validated_data
            )
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"milestone": _milestone_summary(milestone), "intent": serialize_intent(intent)},
            status=status.HTTP_201_CREATED,
        )


class AssignReviewersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, milestone_id):
        serializer = AssignReviewersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = get_object_or_404(Milestone, pk=milestone_id)
        try:
            intent = services.assign_reviewers(
                request.user,
                milestone,
                reviewer_ids=serializer.validated_data["reviewer_ids"],
                required_approvals=serializer.validated_data["required_approvals"],
            )
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"intent": serialize_intent(intent)}, status=status.HTTP_201_CREATED)


class SubmitMilestoneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, milestone_id):
        serializer = SubmitMilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = get_object_or_404(Milestone, pk=milestone_id)
        try:
            intent = services.submit_milestone(
                milestone, request.user, serializer.validated_data
            )
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"intent": serialize_intent(intent)}, status=status.HTTP_201_CREATED)


class CriteriaListCreateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        criteria = VerificationCriteria.objects.filter(active=True).order_by("-version")
        return Response(
            {
                "results": [
                    {
                        "id": item.id,
                        "version": item.version,
                        "criteria_uri": item.criteria_uri,
                        "criteria_hash": bytes(item.criteria_hash).hex(),
                        "onchain_pda": item.onchain_template_pda,
                        "published_at": item.published_at,
                    }
                    for item in criteria
                ]
            }
        )

    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CriteriaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            criteria, intent = services.publish_criteria(
                request.user, serializer.validated_data
            )
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "criteria": {
                    "id": criteria.id,
                    "version": criteria.version,
                    "criteria_uri": criteria.criteria_uri,
                    "criteria_hash": bytes(criteria.criteria_hash).hex(),
                    "onchain_pda": criteria.onchain_template_pda,
                },
                "intent": serialize_intent(intent),
            },
            status=status.HTTP_201_CREATED,
        )


class MilestoneExpireView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, milestone_id):
        milestone = get_object_or_404(Milestone, pk=milestone_id)
        try:
            intent = services.expire_round(request.user, milestone)
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"intent": serialize_intent(intent)}, status=status.HTTP_201_CREATED)


def _roadmap_summary(roadmap: Roadmap) -> dict:
    return {
        "id": roadmap.id,
        "project_id": roadmap.project_id,
        "title": roadmap.title,
        "description": roadmap.description,
        "order": roadmap.order,
    }


class RoadmapCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        serializer = RoadmapCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=project_id)
        try:
            roadmap = services.create_roadmap(project, request.user, serializer.validated_data)
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_roadmap_summary(roadmap), status=status.HTTP_201_CREATED)


class RoadmapUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, roadmap_id):
        serializer = RoadmapUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        roadmap = get_object_or_404(Roadmap, pk=roadmap_id)
        try:
            roadmap = services.update_roadmap(roadmap, request.user, serializer.validated_data)
        except services.MilestoneError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_roadmap_summary(roadmap))
