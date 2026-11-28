import datetime as dt
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from solders.keypair import Keypair

from apps.accounts.models import User, UserRole, Wallet
from apps.chain.models import ProcessedSignature
from apps.milestones.models import Milestone, MilestoneStatus, VerificationCriteria
from apps.projects.models import ApplicationStatus, Project
from apps.reviews.models import Review, Reviewer

TEST_SETTINGS = dict(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    REDIS_URL="redis://127.0.0.1:6380/15",
    SIWS_DOMAIN="localhost:3000",
    SIWS_URI="http://localhost:3000",
    SIWS_CHAIN_ID="devnet",
)

CRITERIA_HASH = "c" * 64
CRITERIA_URI = "https://example.test/criteria/v1"


def wallet_address() -> str:
    return str(Keypair().pubkey())


def fake_transaction(*, signers: list[str], account: str) -> dict:
    program_id = settings.PROGRAM_ID
    account_keys = [*signers, account, program_id]
    return {
        "slot": 4242,
        "blockTime": 1_700_000_000,
        "meta": {"err": None},
        "transaction": {
            "message": {
                "accountKeys": account_keys,
                "header": {"numRequiredSignatures": len(signers)},
                "instructions": [
                    {
                        "programIdIndex": len(account_keys) - 1,
                        "accounts": list(range(len(account_keys) - 1)),
                        "data": "3XZZ984toC4WXCLkxBsLimpEGgH75TKXRJnk",
                    }
                ],
            }
        },
    }


@override_settings(**TEST_SETTINGS)
class Phase0FlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(role=UserRole.ADMIN, is_staff=True, is_superuser=True)
        self.admin_wallet = Wallet.objects.create(
            user=self.admin, address=wallet_address(), is_primary=True
        )
        self.founder = User.objects.create_user(role=UserRole.FOUNDER)
        self.founder_wallet = Wallet.objects.create(
            user=self.founder, address=wallet_address(), is_primary=True
        )
        self.reviewer = User.objects.create_user(role=UserRole.REVIEWER)
        self.reviewer_wallet = Wallet.objects.create(
            user=self.reviewer, address=wallet_address(), is_primary=True
        )
        self.reviewer_two = User.objects.create_user(role=UserRole.REVIEWER)
        self.reviewer_two_wallet = Wallet.objects.create(
            user=self.reviewer_two, address=wallet_address(), is_primary=True
        )
        self.reviewer_three = User.objects.create_user(role=UserRole.REVIEWER)
        self.reviewer_three_wallet = Wallet.objects.create(
            user=self.reviewer_three, address=wallet_address(), is_primary=True
        )

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def confirm(self, client, intent: dict, *, signature=None):
        signers = [intent["payload"]["signer"]]
        account = intent["payload"]["account"]
        signature = signature or ("5" * 88)
        with patch(
            "apps.chain.services.rpc.get_transaction",
            return_value=fake_transaction(signers=signers, account=account),
        ):
            return client.post(
                f"/api/chain/intents/{intent['id']}/confirm/",
                {"signature": signature},
                format="json",
            )

    def create_project(self):
        response = self.client_for(self.founder).post(
            "/api/projects/",
            {
                "name": "Orbit Tools",
                "description": "A developer tooling project with verifiable milestones.",
                "website": "https://orbit.example",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def publish_criteria(self) -> str:
        response = self.client_for(self.admin).post(
            "/api/admin/criteria/",
            {"version": 1, "criteria_hash": CRITERIA_HASH, "criteria_uri": CRITERIA_URI},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        criteria_id = response.json()["criteria"]["id"]
        confirmed = self.confirm(self.client_for(self.admin), response.json()["intent"])
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        criteria = VerificationCriteria.objects.get(pk=criteria_id)
        self.assertTrue(criteria.onchain_template_pda)
        return criteria_id

    def approve_and_accept(self, project_id):
        founder_client = self.client_for(self.founder)
        submitted = founder_client.post(f"/api/projects/{project_id}/submit/")
        self.assertEqual(submitted.status_code, 200, submitted.content)

        approved = self.client_for(self.admin).post(
            f"/api/projects/{project_id}/decision/",
            {"decision": "approve", "notes": "Looks good."},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        confirmed = self.confirm(self.client_for(self.admin), approved.json()["intent"])
        self.assertEqual(confirmed.status_code, 200, confirmed.content)

        pending = founder_client.get(
            f"/api/chain/intents/pending/?object_type=project&object_id={project_id}"
        )
        self.assertEqual(pending.status_code, 200, pending.content)
        accept = next(
            item for item in pending.json()["results"] if item["intent"] == "project.accept_authority"
        )
        accepted = self.confirm(founder_client, accept)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.chain_authority, self.founder_wallet.address)
        return project

    def create_milestone(self, project_id, criteria_id, required_approvals=2, roadmap_id=None):
        payload = {
            "title": "Ship the indexer",
            "description": "Deliver a working indexer with backfill and a public status page.",
            "deadline": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
            "required_approvals": required_approvals,
            "criteria_id": criteria_id,
        }
        if roadmap_id:
            payload["roadmap_id"] = roadmap_id
        response = self.client_for(self.founder).post(
            f"/api/projects/{project_id}/milestones/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        milestone_id = response.json()["milestone"]["id"]
        confirmed = self.confirm(self.client_for(self.founder), response.json()["intent"])
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        return milestone_id

    def register_reviewer(self, user, wallet) -> str:
        response = self.client_for(self.admin).post(
            "/api/admin/reviewers/", {"wallet_address": wallet.address}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        reviewer_id = response.json()["reviewer"]["id"]
        confirmed = self.confirm(self.client_for(self.admin), response.json()["intent"])
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        return reviewer_id

    def test_full_slice(self):
        criteria_id = self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])

        profile = self.client_for(self.founder).put(
            "/api/founders/me/",
            {"display_name": "Orbit founder", "bio": "Building verifiable tooling."},
            format="json",
        )
        self.assertEqual(profile.status_code, 200, profile.content)

        roadmap = self.client_for(self.founder).post(
            f"/api/projects/{project['id']}/roadmaps/",
            {
                "title": "Indexer delivery",
                "description": "The first public delivery track.",
                "order": 1,
            },
            format="json",
        )
        self.assertEqual(roadmap.status_code, 201, roadmap.content)
        roadmap_id = roadmap.json()["id"]

        outsider_roadmap = self.client_for(self.reviewer_three).post(
            f"/api/projects/{project['id']}/roadmaps/",
            {"title": "Unauthorized", "order": 2},
            format="json",
        )
        self.assertEqual(outsider_roadmap.status_code, 400)

        milestone_id = self.create_milestone(
            project["id"], criteria_id, required_approvals=2, roadmap_id=roadmap_id
        )

        reviewer_one = self.register_reviewer(self.reviewer, self.reviewer_wallet)
        reviewer_two = self.register_reviewer(self.reviewer_two, self.reviewer_two_wallet)

        assigned = self.client_for(self.admin).post(
            f"/api/milestones/{milestone_id}/assign/",
            {"reviewer_ids": [reviewer_one, reviewer_two], "required_approvals": 2},
            format="json",
        )
        self.assertEqual(assigned.status_code, 201, assigned.content)
        self.assertEqual(
            self.confirm(self.client_for(self.admin), assigned.json()["intent"]).status_code, 200
        )

        submitted = self.client_for(self.founder).post(
            f"/api/milestones/{milestone_id}/submit/",
            {
                "evidence": [
                    {
                        "kind": "repo",
                        "uri": "https://github.com/orbit/indexer/pull/1",
                        "sha256": "a" * 64,
                        "content_type": "text/html",
                        "size_bytes": 1234,
                    },
                    {
                        "kind": "document",
                        "uri": "https://example.test/orbit/indexer-report.pdf",
                        "sha256": "b" * 64,
                        "content_type": "application/pdf",
                        "size_bytes": 4096,
                    },
                ],
                # A founder-supplied criteria field must be ignored by the serializer.
                "criteria_hash": "d" * 64,
                "criteria_uri": "https://evil.example/criteria",
            },
            format="json",
        )
        self.assertEqual(submitted.status_code, 201, submitted.content)
        self.assertEqual(
            self.confirm(self.client_for(self.founder), submitted.json()["intent"]).status_code, 200
        )
        milestone = Milestone.objects.get(pk=milestone_id)
        self.assertEqual(milestone.status, MilestoneStatus.SUBMITTED)
        self.assertEqual(milestone.current_round, 1)
        submission = milestone.submissions.get(round=1)
        self.assertEqual(bytes(submission.criteria_hash).hex(), CRITERIA_HASH)
        self.assertEqual(submission.criteria_uri, CRITERIA_URI)

        first_verdict = self.client_for(self.reviewer).post(
            f"/api/milestones/{milestone_id}/review/",
            {"decision": "verify", "comment": "Evidence and repo control confirmed."},
            format="json",
        )
        self.assertEqual(first_verdict.status_code, 201, first_verdict.content)
        self.assertEqual(
            self.confirm(self.client_for(self.reviewer), first_verdict.json()["intent"]).status_code,
            200,
        )

        # No reassignment after a verdict in the current round.
        reassign = self.client_for(self.admin).post(
            f"/api/milestones/{milestone_id}/assign/",
            {"reviewer_ids": [reviewer_one, reviewer_two], "required_approvals": 2},
            format="json",
        )
        self.assertEqual(reassign.status_code, 400)

        second_verdict = self.client_for(self.reviewer_two).post(
            f"/api/milestones/{milestone_id}/review/",
            {"decision": "verify", "comment": "Independent confirmation."},
            format="json",
        )
        self.assertEqual(second_verdict.status_code, 201, second_verdict.content)
        self.assertEqual(
            self.confirm(self.client_for(self.reviewer_two), second_verdict.json()["intent"]).status_code,
            200,
        )

        milestone.refresh_from_db()
        self.assertEqual(milestone.status, MilestoneStatus.VERIFIED)
        self.assertEqual(Review.objects.filter(milestone=milestone, round=1).count(), 2)

        public = APIClient().get(f"/api/projects/{Project.objects.get(pk=project['id']).slug}/")
        self.assertEqual(public.status_code, 200, public.content)
        payload = public.json()
        milestone_payload = payload["milestones"][0]
        self.assertEqual(milestone_payload["status"], MilestoneStatus.VERIFIED)
        self.assertEqual(milestone_payload["criteria"]["hash"], CRITERIA_HASH)
        self.assertEqual(len(milestone_payload["reviews"]), 2)
        self.assertEqual(payload["progress"]["verified"], 1)
        self.assertEqual(payload["progress"]["total"], 1)
        self.assertEqual(payload["progress"]["percentage"], 100)
        self.assertEqual(payload["roadmaps"][0]["title"], "Indexer delivery")
        self.assertEqual(milestone_payload["roadmap"]["id"], roadmap_id)
        self.assertEqual(len(milestone_payload["submissions"][0]["evidence"]), 2)
        self.assertEqual(
            milestone_payload["submissions"][0]["evidence"][0]["kind"], "repo"
        )
        self.assertIn("no weighting", payload["progress"]["basis"].lower())
        self.assertIn("not investment advice", str(payload).lower())

        # Dispute path: file, resolve, and publish the record.
        review_id = milestone_payload["reviews"][0]["id"]
        filed = self.client_for(self.reviewer_three).post(
            f"/api/reviews/{review_id}/disputes/",
            {
                "reason": "The linked pull request does not show the claimed deployment evidence."
            },
            format="json",
        )
        self.assertEqual(filed.status_code, 201, filed.content)
        dispute_id = filed.json()["id"]
        resolved = self.client_for(self.admin).post(
            f"/api/disputes/{dispute_id}/resolve/",
            {"status": "upheld", "resolution": "Reviewed; verdict stands with an added note."},
            format="json",
        )
        self.assertEqual(resolved.status_code, 200, resolved.content)
        after_dispute = APIClient().get(f"/api/projects/{project['slug']}/").json()
        disputes = after_dispute["milestones"][0]["reviews"][0]["disputes"]
        self.assertEqual(disputes[0]["status"], "upheld")
        self.assertIn("verdict stands", disputes[0]["resolution"])

        admin_list = self.client_for(self.admin).get("/api/admin/disputes/?status=upheld")
        self.assertEqual(admin_list.status_code, 200)
        self.assertEqual(len(admin_list.json()["results"]), 1)
        forbidden = self.client_for(self.reviewer_three).get("/api/admin/disputes/")
        self.assertEqual(forbidden.status_code, 403)

    def test_single_review_verdicts_are_not_allowed_or_published(self):
        criteria_id = self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])

        # API refuses R=1.
        response = self.client_for(self.founder).post(
            f"/api/projects/{project['id']}/milestones/",
            {
                "title": "Single reviewer",
                "description": "A milestone that must not be published with one reviewer.",
                "deadline": (dt.date.today() + dt.timedelta(days=10)).isoformat(),
                "required_approvals": 1,
                "criteria_id": criteria_id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_founder_cannot_create_milestone_without_criteria(self):
        self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])
        response = self.client_for(self.founder).post(
            f"/api/projects/{project['id']}/milestones/",
            {
                "title": "No criteria",
                "description": "A milestone without an admin-published criteria template.",
                "deadline": (dt.date.today() + dt.timedelta(days=10)).isoformat(),
                "required_approvals": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_founder_cannot_decide_project(self):
        project = self.create_project()
        founder_client = self.client_for(self.founder)
        founder_client.post(f"/api/projects/{project['id']}/submit/")
        decision = founder_client.post(
            f"/api/projects/{project['id']}/decision/", {"decision": "approve"}, format="json"
        )
        self.assertEqual(decision.status_code, 403)

    def test_unassigned_reviewer_cannot_review_and_r_cannot_exceed_n(self):
        criteria_id = self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])
        milestone_id = self.create_milestone(project["id"], criteria_id, required_approvals=2)
        reviewer_one = self.register_reviewer(self.reviewer, self.reviewer_wallet)
        reviewer_two = self.register_reviewer(self.reviewer_two, self.reviewer_two_wallet)
        reviewer_three = self.register_reviewer(self.reviewer_three, self.reviewer_three_wallet)

        # R > N is rejected.
        assigned = self.client_for(self.admin).post(
            f"/api/milestones/{milestone_id}/assign/",
            {"reviewer_ids": [reviewer_one], "required_approvals": 2},
            format="json",
        )
        self.assertEqual(assigned.status_code, 400)

        # Duplicate reviewers are rejected.
        assigned = self.client_for(self.admin).post(
            f"/api/milestones/{milestone_id}/assign/",
            {"reviewer_ids": [reviewer_one, reviewer_one], "required_approvals": 2},
            format="json",
        )
        self.assertEqual(assigned.status_code, 400)

        assigned = self.client_for(self.admin).post(
            f"/api/milestones/{milestone_id}/assign/",
            {"reviewer_ids": [reviewer_one, reviewer_two], "required_approvals": 2},
            format="json",
        )
        self.assertEqual(assigned.status_code, 201, assigned.content)
        self.assertEqual(
            self.confirm(self.client_for(self.admin), assigned.json()["intent"]).status_code, 200
        )

        submitted = self.client_for(self.founder).post(
            f"/api/milestones/{milestone_id}/submit/",
            {
                "evidence": [
                    {
                        "kind": "url",
                        "uri": "https://example.test/evidence",
                        "sha256": "a" * 64,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(submitted.status_code, 201, submitted.content)
        self.assertEqual(
            self.confirm(self.client_for(self.founder), submitted.json()["intent"]).status_code, 200
        )

        # Registered but unassigned reviewer cannot vote.
        verdict = self.client_for(self.reviewer_three).post(
            f"/api/milestones/{milestone_id}/review/",
            {"decision": "verify"},
            format="json",
        )
        self.assertEqual(verdict.status_code, 400)
        self.assertEqual(verdict.json()["error"]["code"], "not_assigned")

    def test_single_review_verdict_is_not_published(self):
        created = self.create_project()
        project = Project.objects.get(pk=created["id"])
        project.application_status = ApplicationStatus.APPROVED
        project.save(update_fields=["application_status", "updated_at"])
        Milestone.objects.create(
            project=project,
            title="Legacy single review",
            description="A legacy R=1 milestone must never be shown as a published verdict.",
            deadline=dt.date.today() + dt.timedelta(days=5),
            status=MilestoneStatus.VERIFIED,
            required_approvals=1,
            created_by=self.founder,
        )
        public = APIClient().get(f"/api/projects/{project.slug}/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["milestones"], [])

    def test_progress_is_verified_over_published_only(self):
        created = self.create_project()
        project = Project.objects.get(pk=created["id"])
        project.application_status = ApplicationStatus.APPROVED
        project.save(update_fields=["application_status", "updated_at"])
        Milestone.objects.create(
            project=project,
            title="Verified item",
            description="A verified milestone for progress calculation.",
            deadline=dt.date.today() + dt.timedelta(days=5),
            status=MilestoneStatus.VERIFIED,
            required_approvals=2,
            created_by=self.founder,
        )
        Milestone.objects.create(
            project=project,
            title="Submitted item",
            description="A submitted milestone for progress calculation.",
            deadline=dt.date.today() + dt.timedelta(days=6),
            status=MilestoneStatus.SUBMITTED,
            required_approvals=2,
            created_by=self.founder,
        )
        # Single-review legacy item is not published.
        Milestone.objects.create(
            project=project,
            title="Legacy item",
            description="A single-review milestone that must not affect progress.",
            deadline=dt.date.today() + dt.timedelta(days=7),
            status=MilestoneStatus.VERIFIED,
            required_approvals=1,
            created_by=self.founder,
        )
        public = APIClient().get(f"/api/projects/{project.slug}/").json()
        self.assertEqual(public["progress"]["verified"], 1)
        self.assertEqual(public["progress"]["total"], 2)
        self.assertEqual(public["progress"]["percentage"], 50)

    def test_evidence_validation_rejects_bad_kinds_and_primary_uri(self):
        criteria_id = self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])
        milestone_id = self.create_milestone(project["id"], criteria_id, required_approvals=2)
        bad_kind = self.client_for(self.founder).post(
            f"/api/milestones/{milestone_id}/submit/",
            {
                "evidence": [
                    {"kind": "video", "uri": "https://example.test/x", "sha256": "a" * 64}
                ]
            },
            format="json",
        )
        self.assertEqual(bad_kind.status_code, 400)
        long_primary = self.client_for(self.founder).post(
            f"/api/milestones/{milestone_id}/submit/",
            {
                "evidence": [
                    {
                        "kind": "url",
                        "uri": "https://example.test/" + ("x" * 140),
                        "sha256": "a" * 64,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(long_primary.status_code, 400)

        javascript_uri = self.client_for(self.founder).post(
            f"/api/milestones/{milestone_id}/submit/",
            {
                "evidence": [
                    {
                        "kind": "url",
                        "uri": "javascript:alert(1)",
                        "sha256": "a" * 64,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(javascript_uri.status_code, 400)

        bad_criteria = self.client_for(self.admin).post(
            "/api/admin/criteria/",
            {
                "version": 2,
                "criteria_hash": "d" * 64,
                "criteria_uri": "javascript:alert(1)",
            },
            format="json",
        )
        self.assertEqual(bad_criteria.status_code, 400)

    def test_indexer_ingest_requires_secret_and_is_idempotent(self):
        criteria_id = self.publish_criteria()
        project = self.create_project()
        self.approve_and_accept(project["id"])
        milestone_id = self.create_milestone(project["id"], criteria_id, required_approvals=2)
        milestone = Milestone.objects.get(pk=milestone_id)

        payload = {
            "signature": "9" * 88,
            "slot": 9001,
            "milestones": [
                {
                    "pda": milestone.onchain_milestone_pda,
                    "status": "verified",
                    "round": 1,
                    "approvals": 2,
                    "rejections": 0,
                }
            ],
        }
        client = APIClient()
        denied = client.post("/api/chain/indexer/ingest/", payload, format="json")
        self.assertEqual(denied.status_code, 403)

        accepted = client.post(
            "/api/chain/indexer/ingest/",
            payload,
            format="json",
            HTTP_X_INDEXER_SECRET=settings.INDEXER_SHARED_SECRET,
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        milestone.refresh_from_db()
        self.assertEqual(milestone.chain_status, "verified")
        self.assertEqual(milestone.chain_slot, 9001)

        duplicate = client.post(
            "/api/chain/indexer/ingest/",
            payload,
            format="json",
            HTTP_X_INDEXER_SECRET=settings.INDEXER_SHARED_SECRET,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["status"], "duplicate")
        self.assertEqual(ProcessedSignature.objects.count(), 1)
