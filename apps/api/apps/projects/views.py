from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chain.services import serialize_intent
from apps.projects.models import ApplicationStatus, Project

from . import services
from .serializers import (
    FounderProfileSerializer,
    ProjectCreateSerializer,
    ProjectDecisionSerializer,
    ProjectTreasurySerializer,
    TokenMintSerializer,
)


def _project_summary(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "website": project.website,
        "category": project.category.name if project.category else None,
        "application_status": project.application_status,
        "lifecycle_status": project.lifecycle_status,
        "data_origin": project.data_origin,
        "token_mint": project.token_mint,
        "treasury_wallet": project.treasury_wallet,
        "treasury_chain": project.treasury_chain,
        "founder": {
            "id": project.founder_id,
            "display_name": project.founder.display_name,
        },
        "chain": {
            "pda": project.onchain_project_pda,
            "signature": project.chain_signature,
            "slot": project.chain_slot,
            "lifecycle_status": project.chain_lifecycle_status,
        },
        "created_at": project.created_at,
    }


class ProjectListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        projects = (
            Project.objects.filter(application_status=ApplicationStatus.APPROVED)
            .select_related("category", "founder")
            .order_by("name")[:100]
        )
        return Response(
            {
                "results": [_project_summary(project) for project in projects],
                "notice": "Information only. Not investment advice. No ranking or endorsement is implied.",
            }
        )

    def post(self, request):
        if request.user.role not in ("founder", "admin"):
            return Response(
                {"error": {"code": "forbidden", "message": "Founder role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project = services.create_project(request.user, serializer.validated_data)
        except services.ProjectError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_project_summary(project), status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(
            Project.objects.select_related("category", "founder"), slug=slug
        )
        can_view_unapproved = request.user.is_authenticated and (
            request.user.is_admin or request.user.id == project.founder_id
        )
        if project.application_status != ApplicationStatus.APPROVED and not can_view_unapproved:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(services.public_project_payload(project))


class ProjectSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        try:
            project = services.submit_project(project, request.user)
        except services.ProjectError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(_project_summary(project))


class ProjectDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=project_id)
        try:
            project, intent = services.decide_project(
                project,
                request.user,
                decision=serializer.validated_data["decision"],
                notes=serializer.validated_data.get("notes", ""),
            )
        except services.ProjectError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "project": _project_summary(project),
                "intent": serialize_intent(intent) if intent else None,
            }
        )


class AdminProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = Project.objects.select_related("category", "founder").order_by("-created_at")
        requested_status = request.query_params.get("status")
        if requested_status:
            if requested_status not in ApplicationStatus.values:
                return Response(
                    {"error": {"code": "validation_error", "message": "Unknown status."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(application_status=requested_status)
        return Response({"results": [_project_summary(project) for project in queryset[:200]]})


class FounderProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "founder_profile", None)
        if profile is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "display_name": profile.display_name,
                "bio": profile.bio,
                "website": profile.website,
            }
        )

    def put(self, request):
        serializer = FounderProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = services.update_founder_profile(request.user, serializer.validated_data)
        return Response(
            {
                "display_name": profile.display_name,
                "bio": profile.bio,
                "website": profile.website,
            }
        )


class FounderProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = (
            Project.objects.filter(founder=request.user)
            .select_related("category", "founder")
            .order_by("-created_at")
        )
        results = []
        for project in projects:
            item = _project_summary(project)
            item["milestones"] = [
                {
                    "id": milestone.id,
                    "title": milestone.title,
                    "status": milestone.status,
                    "deadline": milestone.deadline,
                    "current_round": milestone.current_round,
                    "required_approvals": milestone.required_approvals,
                    "chain_pda": milestone.onchain_milestone_pda,
                }
                for milestone in project.milestones.order_by("deadline")
            ]
            results.append(item)
        return Response({"results": results})


class ManageProjectView(APIView):
    """Owner or admin view, including drafts and chain state."""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            Project.objects.select_related("category", "founder"), pk=project_id
        )
        if not (request.user.is_admin or request.user.id == project.founder_id):
            return Response(
                {"error": {"code": "forbidden", "message": "Not allowed."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(services.public_project_payload(project, include_drafts=True))


class ProjectTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if project.founder_id != request.user.id and not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Not allowed."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = TokenMintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project.token_mint = serializer.validated_data["token_mint"]
        project.save(update_fields=["token_mint", "updated_at"])
        from apps.common.models import AuditLog

        AuditLog.objects.create(
            actor=request.user,
            action="project.token_mint_updated",
            object_type="project",
            object_id=str(project.id),
            metadata={"token_mint": project.token_mint},
        )
        return Response({"id": project.id, "token_mint": project.token_mint})


class ProjectTreasuryUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if project.founder_id != request.user.id and not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Not allowed."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectTreasurySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project.treasury_wallet = serializer.validated_data["treasury_wallet"]
        project.treasury_chain = serializer.validated_data["treasury_chain"]
        project.save(update_fields=["treasury_wallet", "treasury_chain", "updated_at"])
        from apps.common.models import AuditLog

        AuditLog.objects.create(
            actor=request.user,
            action="project.treasury_updated",
            object_type="project",
            object_id=str(project.id),
            metadata={
                "treasury_wallet": project.treasury_wallet,
                "treasury_chain": project.treasury_chain,
            },
        )
        return Response(
            {
                "id": project.id,
                "treasury_wallet": project.treasury_wallet,
                "treasury_chain": project.treasury_chain,
            }
        )


class ProjectTreasuryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        if project.application_status != ApplicationStatus.APPROVED:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not project.treasury_wallet:
            return Response(
                {
                    "linked": False,
                    "notice": "No treasury wallet has been declared for this project.",
                }
            )
        from apps.integrations import treasury
        from apps.integrations.treasury import TreasuryError

        try:
            return Response(
                treasury.get_treasury_snapshot(
                    project.treasury_wallet, project.treasury_chain
                )
            )
        except TreasuryError as exc:
            return Response(
                {
                    "linked": True,
                    "wallet": project.treasury_wallet,
                    "chain": project.treasury_chain,
                    "error": str(exc),
                    "caveats": treasury.CAVEATS,
                }
            )
