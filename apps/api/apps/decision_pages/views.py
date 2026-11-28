from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import ApplicationStatus, Project
from apps.projects.services import public_project_payload

from . import services


class ProjectDecisionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        project = get_object_or_404(
            Project.objects.select_related("category", "founder", "github_account"),
            slug=slug,
        )
        if project.application_status != ApplicationStatus.APPROVED:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(services.build_project_decision(project))


class TokenDecisionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, mint):
        # Jupiter and the RPC client validate the mint; return a clean 400 here.
        from apps.integrations.jupiter import MINT_RE

        if not MINT_RE.match(mint):
            return Response(
                {"error": {"code": "invalid_mint", "message": "Invalid token mint."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(services.build_token_decision(mint))
