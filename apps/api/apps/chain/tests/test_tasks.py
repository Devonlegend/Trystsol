import datetime as dt
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.chain import tasks
from apps.chain.models import SignedIntent
from apps.milestones.models import Milestone
from apps.projects.models import Project


class CeleryTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(role=UserRole.FOUNDER)
        self.project = Project.objects.create(
            founder=self.user,
            name="Task project",
            slug="task-project",
            description="A project used for Celery task tests.",
        )

    def test_prune_expired_intents_only_deletes_old_unconsumed(self):
        old = SignedIntent.objects.create(
            intent="milestone.create",
            object_type="milestone",
            object_id=self.project.id,
            payload={},
            expires_at=timezone.now() - dt.timedelta(days=2),
        )
        fresh = SignedIntent.objects.create(
            intent="milestone.create",
            object_type="milestone",
            object_id=self.project.id,
            payload={},
            expires_at=timezone.now() + dt.timedelta(hours=1),
        )
        consumed = SignedIntent.objects.create(
            intent="milestone.create",
            object_type="milestone",
            object_id=self.project.id,
            payload={},
            expires_at=timezone.now() - dt.timedelta(days=2),
            consumed_at=timezone.now() - dt.timedelta(days=2),
        )
        removed = tasks.prune_expired_intents.run(24)
        self.assertEqual(removed, 1)
        self.assertFalse(SignedIntent.objects.filter(pk=old.pk).exists())
        self.assertTrue(SignedIntent.objects.filter(pk=fresh.pk).exists())
        self.assertTrue(SignedIntent.objects.filter(pk=consumed.pk).exists())

    def test_reconcile_chain_state_reports_missing_accounts(self):
        Milestone.objects.create(
            project=self.project,
            title="Indexed milestone",
            description="A milestone with an on-chain PDA for reconciliation.",
            deadline=dt.date.today() + dt.timedelta(days=5),
            status="submitted",
            required_approvals=2,
            created_by=self.user,
            onchain_milestone_pda="9xQeWvG816bUx9EPjHmaT23yvVM7vA8c9HhF6k9mV1yZ",
        )
        with patch.object(tasks.rpc, "get_account_info", return_value=None):
            result = tasks.reconcile_chain_state.run(10)
        self.assertEqual(result, {"checked": 1, "missing": 1})

    def test_rpc_health_task(self):
        with patch.object(tasks.rpc, "get_health", return_value="ok"):
            self.assertEqual(tasks.check_rpc_health.run(), "ok")


class ProductionSettingsGuardTests(SimpleTestCase):
    def test_production_settings_fail_closed(self):
        from config import settings as project_settings

        with patch.multiple(
            project_settings,
            SECRET_KEY="dev-only-change-me",
            ACCESS_TOKEN_SECRET="short",
            ALLOWED_HOSTS=["*"],
            CORS_ALLOWED_ORIGINS=["http://localhost:3000"],
            SIWS_DOMAIN="localhost:3000",
        ):
            with self.assertRaises(ImproperlyConfigured) as context:
                project_settings.validate_production_settings()
        message = str(context.exception)
        self.assertIn("DJANGO_SECRET_KEY", message)
        self.assertIn("ACCESS_TOKEN_SECRET", message)
        self.assertIn("ALLOWED_HOSTS", message)
        self.assertIn("https", message)
        self.assertIn("SIWS_DOMAIN", message)
