from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class GitHubAccount(UUIDTimeStampedModel):
    """A project repository whose control has been proven by a signed file."""

    project = models.OneToOneField(
        "projects.Project", on_delete=models.CASCADE, related_name="github_account"
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="github_links"
    )
    repo_url = models.URLField(max_length=300)
    repo_owner = models.CharField(max_length=100)
    repo_name = models.CharField(max_length=100)
    github_login = models.CharField(max_length=100, blank=True)
    proof_method = models.CharField(max_length=32, default="signed_file")
    verified_at = models.DateTimeField()
    last_activity = models.JSONField(default=dict, blank=True)
    activity_fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integrations_github_account"
        indexes = [models.Index(fields=["repo_owner", "repo_name"])]

    def __str__(self) -> str:
        return self.repo_url


class GitHubProofChallenge(UUIDTimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="github_challenges"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="github_challenges"
    )
    repo_url = models.URLField(max_length=300)
    repo_owner = models.CharField(max_length=100)
    repo_name = models.CharField(max_length=100)
    nonce = models.CharField(max_length=64, unique=True)
    message = models.TextField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integrations_github_challenge"
        indexes = [models.Index(fields=["user", "project"])]

    def __str__(self) -> str:
        return self.nonce


class TokenCache(UUIDTimeStampedModel):
    """Latest Jupiter token snapshot. Redis is the hot cache; this is the audit trail."""

    mint = models.CharField(max_length=44, unique=True)
    name = models.CharField(max_length=120, blank=True)
    symbol = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict)
    fetched_at = models.DateTimeField()
    source = models.CharField(max_length=64, default="jupiter")

    class Meta:
        db_table = "integrations_token_cache"

    def __str__(self) -> str:
        return self.mint
