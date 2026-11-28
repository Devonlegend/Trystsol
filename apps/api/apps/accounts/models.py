import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import UUIDTimeStampedModel

BASE58_ADDRESS = RegexValidator(
    regex=r"^[1-9A-HJ-NP-Za-km-z]{32,44}$",
    message="Enter a valid base58 Solana address.",
)


class UserRole(models.TextChoices):
    FOUNDER = "founder", "Founder"
    REVIEWER = "reviewer", "Reviewer"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, role=UserRole.FOUNDER, **extra):
        extra.setdefault("is_active", True)
        user = self.model(role=role, **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, **extra):
        extra.setdefault("role", UserRole.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra.get("role") != UserRole.ADMIN:
            raise ValueError("Superuser must have role=admin.")
        return self.create_user(**extra)


class User(AbstractBaseUser, PermissionsMixin, UUIDTimeStampedModel):
    """Custom user from day one, as required by the brief.

    There is no password login: authentication is SIWS only. The UUID primary key is
    the USERNAME_FIELD because no email or handle is required to participate.
    """

    display_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.FOUNDER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=[c[0] for c in UserRole.choices]),
                name="user_role_valid",
            )
        ]

    def __str__(self) -> str:
        return self.display_name or str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN or self.is_superuser


class Wallet(UUIDTimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallets")
    address = models.CharField(max_length=44, unique=True, validators=[BASE58_ADDRESS])
    is_primary = models.BooleanField(default=False)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_wallet"
        constraints = [
            models.UniqueConstraint(fields=["user", "address"], name="wallet_user_address_unique"),
        ]
        indexes = [models.Index(fields=["user"])]

    def __str__(self) -> str:
        return self.address


class SignInChallenge(UUIDTimeStampedModel):
    nonce = models.CharField(max_length=64, unique=True)
    domain = models.CharField(max_length=255)
    uri = models.CharField(max_length=512)
    chain_id = models.CharField(max_length=32)
    statement = models.TextField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    wallet_address = models.CharField(max_length=44, blank=True)
    request_ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "accounts_signin_challenge"
        indexes = [models.Index(fields=["expires_at"])]

    def __str__(self) -> str:
        return self.nonce


class RefreshToken(UUIDTimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaces"
    )
    user_agent_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "accounts_refresh_token"
        indexes = [models.Index(fields=["user", "family_id"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.family_id}"
