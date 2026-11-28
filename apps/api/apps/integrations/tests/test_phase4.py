import base64
import datetime as dt
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from nacl.signing import SigningKey
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole, Wallet
from apps.accounts.siws import base58encode
from apps.decision_pages import services as decision_services
from apps.integrations import github, jupiter, rpc_facts, services as integration_services
from apps.integrations.models import GitHubAccount, GitHubProofChallenge, TokenCache
from apps.milestones.models import Milestone, MilestoneStatus
from apps.passport.services import builder_passport
from apps.projects.models import ApplicationStatus, Project

TEST_SETTINGS = dict(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    JUPITER_BASE_URL="https://api.jup.ag",
    GITHUB_API_URL="https://api.github.com",
    MAINNET_RPC_URL="https://api.mainnet-beta.solana.com",
)

MINT = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
REPO_URL = "https://github.com/example/orbit"


@override_settings(**TEST_SETTINGS)
class IntegrationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.founder = User.objects.create_user(role=UserRole.FOUNDER, display_name="Orbit")
        self.signing_key = SigningKey.generate()
        self.address = base58encode(self.signing_key.verify_key.encode())
        self.wallet = Wallet.objects.create(
            user=self.founder, address=self.address, is_primary=True
        )
        self.project = Project.objects.create(
            founder=self.founder,
            name="Orbit",
            slug="orbit",
            description="A project with automated facts.",
            application_status=ApplicationStatus.APPROVED,
            token_mint=MINT,
        )


class JupiterClientTests(IntegrationTestCase):
    def test_token_and_price_are_cached_and_recorded(self):
        token_payload = [
            {
                "id": MINT,
                "name": "Jupiter",
                "symbol": "JUP",
                "decimals": 6,
                "isVerified": True,
                "organicScore": 98.4,
                "organicScoreLabel": "high",
                "holderCount": 838275,
                "usdPrice": 0.32,
                "audit": {"mintAuthorityDisabled": True},
            }
        ]
        price_payload = {MINT: {"usdPrice": 0.32, "priceChange24h": -1.2, "blockId": 123}}

        def fake_get(path, params):
            if path == "/tokens/v2/search":
                return token_payload
            if path == "/price/v3":
                return price_payload
            raise AssertionError(path)

        with patch.object(jupiter, "_get", side_effect=fake_get) as mocked:
            snapshot = jupiter.token_snapshot(MINT)
            again = jupiter.token_snapshot(MINT)

        self.assertEqual(snapshot["token"]["name"], "Jupiter")
        self.assertEqual(snapshot["price"]["blockId"], 123)
        self.assertEqual(mocked.call_count, 2)  # token + price, second call cached
        self.assertTrue(TokenCache.objects.filter(mint=MINT).exists())

    def test_unknown_token_raises(self):
        with patch.object(jupiter, "_get", return_value=[]):
            with self.assertRaises(jupiter.IntegrationError):
                jupiter.fetch_token(MINT)


class MintFactsTests(IntegrationTestCase):
    def test_parses_mainnet_mint(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "result": {
                        "value": {
                            "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                            "data": {
                                "parsed": {
                                    "info": {
                                        "decimals": 6,
                                        "supply": "1000000000",
                                        "mintAuthority": None,
                                        "freezeAuthority": None,
                                        "isInitialized": True,
                                    }
                                }
                            },
                        }
                    }
                },
            },
        )()
        with patch("apps.integrations.rpc_facts.httpx.post", return_value=response):
            facts = rpc_facts.get_mint_facts(MINT)
        self.assertTrue(facts["found"])
        self.assertEqual(facts["decimals"], 6)
        self.assertIsNone(facts["mint_authority"])


class GitHubClientTests(TestCase):
    def test_rejects_non_github_and_arbitrary_hosts(self):
        for value in ("https://evil.example/owner/repo", "https://github.com/only-one"):
            with self.assertRaises(github.GitHubError):
                github.parse_repo_url(value)

    def test_parses_github_url_and_canonicalises(self):
        owner, repo, canonical = github.parse_repo_url("https://github.com/example/orbit.git/")
        self.assertEqual((owner, repo), ("example", "orbit"))
        self.assertEqual(canonical, "https://github.com/example/orbit")

    def test_activity_counts_commits(self):
        with patch.object(github, "fetch_repo", return_value={"full_name": "example/orbit"}), patch.object(
            github, "fetch_commits_since", return_value=7
        ):
            activity = github.fetch_activity("example", "orbit", "2026-11-01T00:00:00Z")
        self.assertEqual(activity["commits_since"], 7)


class GitHubProofTests(IntegrationTestCase):
    def _proof(self, message: str, key: SigningKey | None = None) -> str:
        signature = (key or self.signing_key).sign(message.encode()).signature
        return json.dumps(
            {
                "address": self.address,
                "message": message,
                "signature": base64.b64encode(signature).decode(),
            }
        )

    def test_signed_file_proof_links_repository(self):
        challenge = integration_services.create_challenge(
            self.founder, self.project, REPO_URL
        )
        with patch.object(
            integration_services.github,
            "fetch_file",
            return_value=self._proof(challenge.message),
        ), patch.object(
            integration_services.github,
            "fetch_repo",
            return_value={"owner": "example", "full_name": "example/orbit"},
        ):
            account = integration_services.verify_challenge(self.founder, challenge)

        self.assertEqual(account.repo_url, REPO_URL)
        self.assertTrue(GitHubAccount.objects.filter(project=self.project).exists())
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.consumed_at)
        with self.assertRaises(integration_services.ProofError):
            integration_services.verify_challenge(self.founder, challenge)

    def test_bad_signature_is_rejected(self):
        challenge = integration_services.create_challenge(
            self.founder, self.project, REPO_URL
        )
        other = SigningKey.generate()
        with patch.object(
            integration_services.github,
            "fetch_file",
            return_value=self._proof(challenge.message, other),
        ), patch.object(
            integration_services.github,
            "fetch_repo",
            return_value={"owner": "example"},
        ):
            with self.assertRaises(integration_services.ProofError):
                integration_services.verify_challenge(self.founder, challenge)


class DecisionPayloadTests(IntegrationTestCase):
    def test_project_decision_has_sourced_facts_and_reviewed_claims(self):
        GitHubAccount.objects.create(
            project=self.project,
            linked_by=self.founder,
            repo_url=REPO_URL,
            repo_owner="example",
            repo_name="orbit",
            verified_at=timezone.now(),
        )
        snapshot = {
            "token": {
                "mint": MINT,
                "name": "Jupiter",
                "symbol": "JUP",
                "decimals": 6,
                "isVerified": True,
                "organicScore": 90,
                "organicScoreLabel": "high",
                "holderCount": 100,
                "audit": {"mintAuthorityDisabled": True},
            },
            "price": {"usdPrice": 0.3, "priceChange24h": 1.0, "blockId": 10},
            "price_error": None,
        }
        with patch.object(decision_services.jupiter, "token_snapshot", return_value=snapshot), patch.object(
            decision_services.rpc_facts,
            "get_mint_facts",
            return_value={
                "found": True,
                "decimals": 6,
                "supply": "1000",
                "mint_authority": None,
                "freeze_authority": None,
                "owner_program": "Tokenkeg",
            },
        ), patch.object(
            decision_services.github,
            "fetch_activity",
            return_value={
                "full_name": "example/orbit",
                "stargazers_count": 5,
                "forks_count": 1,
                "open_issues_count": 2,
                "pushed_at": "2026-11-01T00:00:00Z",
                "commits_since": 3,
                "archived": False,
                "visibility": "public",
                "default_branch": "main",
            },
        ):
            payload = decision_services.build_project_decision(self.project)

        self.assertEqual(payload["project"], "orbit")
        self.assertIn("reviewed", payload)
        titles = [section["title"] for section in payload["automated_sections"]]
        self.assertIn("Jupiter token data (Mainnet)", titles)
        self.assertIn("On-chain mint facts (Mainnet)", titles)
        self.assertIn("GitHub repository activity", titles)
        for section in payload["automated_sections"]:
            for fact in section["facts"]:
                self.assertTrue(fact["source"])
                self.assertTrue(fact["caveat"])
                self.assertIsNotNone(fact["fetched_at"])

    def test_token_decision_has_no_reviewed_claims(self):
        with patch.object(
            decision_services.jupiter,
            "token_snapshot",
            side_effect=jupiter.IntegrationError("unavailable"),
        ), patch.object(
            decision_services.rpc_facts,
            "get_mint_facts",
            side_effect=rpc_facts.RpcFactError("unavailable"),
        ):
            payload = decision_services.build_token_decision(MINT)
        self.assertNotIn("reviewed", payload)
        self.assertTrue(payload["automated_sections"])


class PassportTests(IntegrationTestCase):
    def test_passport_uses_only_multi_review_verified_milestones(self):
        Milestone.objects.create(
            project=self.project,
            title="Verified",
            description="A verified milestone.",
            deadline=dt.date.today() + dt.timedelta(days=1),
            status=MilestoneStatus.VERIFIED,
            required_approvals=2,
            created_by=self.founder,
        )
        Milestone.objects.create(
            project=self.project,
            title="Single review",
            description="A legacy single-review milestone.",
            deadline=dt.date.today() + dt.timedelta(days=2),
            status=MilestoneStatus.VERIFIED,
            required_approvals=1,
            created_by=self.founder,
        )
        passport = builder_passport(self.founder)
        self.assertEqual(passport["verified_milestones"], 1)
        self.assertEqual(passport["entries"][0]["milestone"]["title"], "Verified")
        self.assertIn("No score", passport["notice"])


@override_settings(**TEST_SETTINGS)
class Phase4EndpointTests(IntegrationTestCase):
    def test_project_and_token_decision_endpoints(self):
        client = APIClient()
        with patch.object(decision_services, "build_project_decision", return_value={"ok": True}):
            project_response = client.get("/api/decision/projects/orbit/")
        self.assertEqual(project_response.status_code, 200)
        with patch.object(decision_services, "build_token_decision", return_value={"ok": True}):
            token_response = client.get(f"/api/decision/tokens/{MINT}/")
        self.assertEqual(token_response.status_code, 200)
        bad = client.get("/api/decision/tokens/0notamint/")
        self.assertEqual(bad.status_code, 400)

    def test_passport_endpoint(self):
        response = APIClient().get(f"/api/passport/{self.founder.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["builder"]["display_name"], "Orbit")

    def test_github_challenge_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.founder)
        response = client.post(
            "/api/integrations/github/challenge/",
            {"project_id": str(self.project.id), "repo_url": REPO_URL},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn(self.address, response.json()["message"])
        self.assertEqual(response.json()["file_path"], ".trystsol/proof.json")

    def test_token_mint_update_permissions(self):
        outsider = User.objects.create_user(role=UserRole.FOUNDER)
        client = APIClient()
        client.force_authenticate(user=outsider)
        denied = client.patch(f"/api/projects/{self.project.id}/token/", {"token_mint": MINT})
        self.assertEqual(denied.status_code, 403)

        client.force_authenticate(user=self.founder)
        accepted = client.patch(f"/api/projects/{self.project.id}/token/", {"token_mint": MINT})
        self.assertEqual(accepted.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.token_mint, MINT)
