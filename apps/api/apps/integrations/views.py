from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from . import services
from .models import GitHubAccount, GitHubProofChallenge
from .serializers import GitHubChallengeRequest, GitHubVerifyRequest


class GitHubChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GitHubChallengeRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=serializer.validated_data["project_id"])
        try:
            challenge = services.create_challenge(
                request.user, project, serializer.validated_data["repo_url"]
            )
        except services.ProofError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "challenge_id": challenge.id,
                "repo_url": challenge.repo_url,
                "nonce": challenge.nonce,
                "message": challenge.message,
                "expires_at": challenge.expires_at,
                "file_path": services.PROOF_PATH,
                "instructions": (
                    "Sign the message with the linked wallet, then commit "
                    ".trystsol/proof.json containing "
                    '{"address": "...", "message": "...", "signature": "<base64>"} '
                    "to the repository default branch."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class GitHubVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GitHubVerifyRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = get_object_or_404(
            GitHubProofChallenge, pk=serializer.validated_data["challenge_id"]
        )
        try:
            account = services.verify_challenge(request.user, challenge)
        except services.ProofError as exc:
            return Response(
                {"error": {"code": exc.code, "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "repo_url": account.repo_url,
                "repo_owner": account.repo_owner,
                "repo_name": account.repo_name,
                "proof_method": account.proof_method,
                "verified_at": account.verified_at,
            }
        )


class GitHubStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if project.founder_id != request.user.id and not request.user.is_admin:
            return Response(status=status.HTTP_404_NOT_FOUND)
        account = GitHubAccount.objects.filter(project=project).first()
        if account is None:
            return Response({"linked": False})
        return Response(
            {
                "linked": True,
                "repo_url": account.repo_url,
                "repo_owner": account.repo_owner,
                "repo_name": account.repo_name,
                "proof_method": account.proof_method,
                "verified_at": account.verified_at,
            }
        )
