from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User, UserRole, Wallet
from apps.accounts.siws import SIWSError, b58decode


class Command(BaseCommand):
    help = "Create or update the Devnet users used by the Phase 0 end-to-end script."

    def add_arguments(self, parser):
        parser.add_argument("--admin", required=True)
        parser.add_argument("--founder", required=True)
        parser.add_argument("--reviewer", required=True)
        parser.add_argument("--reviewer2", required=False)

    def handle(self, *args, **options):
        with transaction.atomic():
            users = [
                (UserRole.ADMIN, options["admin"]),
                (UserRole.FOUNDER, options["founder"]),
                (UserRole.REVIEWER, options["reviewer"]),
            ]
            if options.get("reviewer2"):
                users.append((UserRole.REVIEWER, options["reviewer2"]))
            for role, address in users:
                try:
                    if len(b58decode(address)) != 32:
                        raise SIWSError("Address is not 32 bytes.")
                except SIWSError as exc:
                    raise CommandError(f"Invalid wallet address {address}: {exc}") from exc

                wallet = Wallet.objects.filter(address=address).select_related("user").first()
                if wallet:
                    user = wallet.user
                    user.role = role
                    user.is_active = True
                    if role == UserRole.ADMIN:
                        user.is_staff = True
                    user.save(update_fields=["role", "is_active", "is_staff", "updated_at"])
                else:
                    user = User.objects.create_user(
                        role=role,
                        display_name=f"Devnet {role.title()}",
                        is_staff=role == UserRole.ADMIN,
                    )
                    Wallet.objects.create(user=user, address=address, is_primary=True)
                self.stdout.write(f"{role}: {address} -> user {user.id}")
