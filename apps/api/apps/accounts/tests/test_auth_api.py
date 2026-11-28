import base64
import datetime as dt
from unittest.mock import patch

from django.conf import settings as django_settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from nacl.signing import SigningKey
from rest_framework.test import APIClient

from apps.accounts import nonce_store
from apps.accounts.models import RefreshToken, SignInChallenge, User, Wallet
from apps.accounts.siws import base58encode, build_message
from apps.accounts.throttles import AuthRateThrottle

TEST_SETTINGS = dict(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    REDIS_URL="redis://127.0.0.1:6380/15",
    SIWS_DOMAIN="localhost:3000",
    SIWS_URI="http://localhost:3000",
    SIWS_CHAIN_ID="devnet",
    ACCESS_TOKEN_TTL_SECONDS=900,
)


@override_settings(**TEST_SETTINGS)
class AuthApiTests(TestCase):
    def setUp(self):
        nonce_store.clear_all()
        cache.clear()
        self.client = APIClient()
        self.signing_key = SigningKey.generate()
        self.address = base58encode(self.signing_key.verify_key.encode())

    def _challenge(self):
        response = self.client.post("/api/auth/nonce/")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def _message(self, challenge, *, domain=None, nonce=None):
        return build_message(
            domain=domain or challenge["domain"],
            address=self.address,
            statement=challenge["statement"],
            uri=challenge["uri"],
            version="1",
            chain_id=challenge["chainId"],
            nonce=nonce or challenge["nonce"],
            issued_at=challenge["issuedAt"],
            expiration_time=challenge["expirationTime"],
        )

    def _sign(self, message: str, key: SigningKey | None = None) -> str:
        signature = (key or self.signing_key).sign(message.encode("utf-8")).signature
        return base64.b64encode(signature).decode("ascii")

    def _login(self):
        challenge = self._challenge()
        message = self._message(challenge)
        response = self.client.post(
            "/api/auth/verify/",
            {"message": message, "signature": self._sign(message)},
            format="json",
        )
        return response

    def test_sign_in_creates_user_wallet_and_tokens(self):
        response = self._login()
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        self.assertEqual(body["wallet"]["address"], self.address)

        user = User.objects.get(pk=body["user"]["id"])
        self.assertEqual(user.role, "founder")
        self.assertTrue(Wallet.objects.filter(user=user, address=self.address).exists())
        self.assertEqual(SignInChallenge.objects.filter(consumed_at__isnull=False).count(), 1)

    def test_nonce_is_single_use(self):
        challenge = self._challenge()
        message = self._message(challenge)
        signature = self._sign(message)

        first = self.client.post(
            "/api/auth/verify/", {"message": message, "signature": signature}, format="json"
        )
        self.assertEqual(first.status_code, 200, first.content)

        replay = self.client.post(
            "/api/auth/verify/", {"message": message, "signature": signature}, format="json"
        )
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.json()["error"]["code"], "siws_invalid")

    def test_wrong_domain_rejected(self):
        challenge = self._challenge()
        message = self._message(challenge, domain="evil.example")
        response = self.client.post(
            "/api/auth/verify/", {"message": message, "signature": self._sign(message)}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Domain", response.json()["error"]["message"])
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_signature_rejected(self):
        challenge = self._challenge()
        message = self._message(challenge)
        other_key = SigningKey.generate()
        response = self.client.post(
            "/api/auth/verify/", {"message": message, "signature": self._sign(message, other_key)}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Signature", response.json()["error"]["message"])
        self.assertEqual(User.objects.count(), 0)

    def test_expired_challenge_rejected(self):
        challenge = self._challenge()
        message = self._message(challenge)
        SignInChallenge.objects.filter(nonce=challenge["nonce"]).update(
            expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        )
        response = self.client.post(
            "/api/auth/verify/", {"message": message, "signature": self._sign(message)}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_me_requires_auth(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_me_returns_user_with_token(self):
        login = self._login().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["wallets"][0]["address"], self.address)

    def test_refresh_cookie_is_httponly_and_works_without_body(self):
        login = self._login()
        cookie = login.cookies[django_settings.REFRESH_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        old_value = cookie.value

        rotated = self.client.post("/api/auth/refresh/", {}, format="json")
        self.assertEqual(rotated.status_code, 200, rotated.content)
        new_cookie = rotated.cookies[django_settings.REFRESH_COOKIE_NAME]
        self.assertNotEqual(new_cookie.value, old_value)

        logged_out = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logged_out.status_code, 204)
        self.assertEqual(
            logged_out.cookies[django_settings.REFRESH_COOKIE_NAME].value, ""
        )

    def test_refresh_rotation_and_reuse_detection(self):
        login = self._login().json()
        first_refresh = login["refresh"]

        rotated = self.client.post("/api/auth/refresh/", {"refresh": first_refresh}, format="json")
        self.assertEqual(rotated.status_code, 200, rotated.content)
        second_refresh = rotated.json()["refresh"]
        self.assertNotEqual(first_refresh, second_refresh)

        reuse = self.client.post("/api/auth/refresh/", {"refresh": first_refresh}, format="json")
        self.assertEqual(reuse.status_code, 401)

        # Reuse revokes the whole family, including the replacement.
        after = self.client.post("/api/auth/refresh/", {"refresh": second_refresh}, format="json")
        self.assertEqual(after.status_code, 401)
        self.assertEqual(RefreshToken.objects.filter(revoked_at__isnull=True).count(), 0)

    def test_auth_endpoints_are_rate_limited(self):
        with patch.object(AuthRateThrottle, "THROTTLE_RATES", {"auth": "2/min"}):
            cache.clear()
            first = self.client.post("/api/auth/nonce/")
            second = self.client.post("/api/auth/nonce/")
            third = self.client.post("/api/auth/nonce/")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(third.status_code, 429)
