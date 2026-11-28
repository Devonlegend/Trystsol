import hashlib
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import UserRole
from .serializers import LogoutRequest, RefreshRequest, VerifySIWSRequest
from .siws import SIWSError
from .throttles import AuthRateThrottle
from .tokens import TokenError, revoke_refresh, rotate_refresh

logger = logging.getLogger(__name__)


def _ip_hash(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    ip = forwarded or request.META.get("REMOTE_ADDR", "")
    return hashlib.sha256(ip.encode("utf-8")).hexdigest() if ip else ""


def _set_refresh_cookie(response, raw_token: str) -> Response:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        raw_token,
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 86400,
        httponly=True,
        secure=not settings.DEBUG,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )
    return response


def _clear_refresh_cookie(response) -> Response:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    return response


def _agent_hash(request) -> str:
    agent = request.META.get("HTTP_USER_AGENT", "")
    return hashlib.sha256(agent.encode("utf-8")).hexdigest() if agent else ""


class NonceView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        challenge = services.create_challenge(request_ip_hash=_ip_hash(request))
        return Response(services.challenge_payload(challenge), status=status.HTTP_201_CREATED)


class VerifyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = VerifySIWSRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, wallet, tokens = services.verify_and_issue(
                message=serializer.validated_data["message"],
                signature=serializer.validated_data["signature"],
                user_agent_hash=_agent_hash(request),
            )
        except SIWSError as exc:
            logger.info("siws_rejected", extra={"path": request.path, "error_code": "siws_invalid"})
            return Response(
                {"error": {"code": "siws_invalid", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = Response(
            {
                **tokens,
                "user": {
                    "id": str(user.id),
                    "display_name": user.display_name,
                    "role": user.role,
                },
                "wallet": {"address": wallet.address, "is_primary": wallet.is_primary},
            }
        )
        return _set_refresh_cookie(response, tokens["refresh"])


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = RefreshRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data.get("refresh") or request.COOKIES.get(
            settings.REFRESH_COOKIE_NAME, ""
        )
        if not raw:
            return Response(
                {"error": {"code": "refresh_missing", "message": "Refresh token is required."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            tokens = rotate_refresh(raw, user_agent_hash=_agent_hash(request))
        except TokenError as exc:
            return Response(
                {"error": {"code": "refresh_invalid", "message": str(exc)}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        response = Response(tokens)
        return _set_refresh_cookie(response, tokens["refresh"])


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LogoutRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data.get("refresh") or request.COOKIES.get(
            settings.REFRESH_COOKIE_NAME, ""
        )
        if raw:
            revoke_refresh(raw)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return _clear_refresh_cookie(response)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        wallets = [
            {"address": wallet.address, "is_primary": wallet.is_primary, "linked_at": wallet.linked_at}
            for wallet in user.wallets.all().order_by("-is_primary", "linked_at")
        ]
        return Response(
            {
                "id": str(user.id),
                "display_name": user.display_name,
                "role": user.role,
                "is_admin": user.is_admin,
                "wallets": wallets,
            }
        )


class UpdateMeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        display_name = request.data.get("display_name", "")
        if not isinstance(display_name, str) or len(display_name) > 120:
            return Response(
                {"error": {"code": "validation_error", "message": "display_name must be <= 120 chars."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.display_name = display_name
        request.user.save(update_fields=["display_name", "updated_at"])
        return Response({"id": str(request.user.id), "display_name": display_name})


class SetRoleView(APIView):
    """Admin-only role assignment. Phase 0 needs it to appoint a reviewer."""

    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if not request.user.is_admin:
            return Response(
                {"error": {"code": "forbidden", "message": "Administrator role required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        role = request.data.get("role")
        if role not in UserRole.values:
            return Response(
                {"error": {"code": "validation_error", "message": "Invalid role."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .models import User

        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return Response(status=status.HTTP_404_NOT_FOUND)
        user.role = role
        user.save(update_fields=["role", "updated_at"])
        return Response({"id": str(user.id), "role": user.role})
