from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import User
from .tokens import TokenError, decode_access_token


class JWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise AuthenticationFailed("Malformed Authorization header.")

        try:
            payload = decode_access_token(header[1].decode())
        except TokenError as exc:
            raise AuthenticationFailed(str(exc)) from exc

        try:
            user = User.objects.get(pk=payload["sub"])
        except (User.DoesNotExist, KeyError, ValueError) as exc:
            raise AuthenticationFailed("Unknown user.") from exc

        if not user.is_active:
            raise AuthenticationFailed("User is inactive.")

        return user, payload

    def authenticate_header(self, request):
        return self.keyword
