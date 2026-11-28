from django import forms
from django.contrib import admin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import RefreshToken, SignInChallenge, User, Wallet


class UserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "role", "is_active", "is_staff", "is_superuser")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserCreationForm
    list_display = ("id", "display_name", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("id", "display_name", "wallets__address")
    readonly_fields = ("id", "created_at", "updated_at", "last_login")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("address", "user", "is_primary", "linked_at")
    search_fields = ("address",)
    readonly_fields = ("id", "linked_at")


@admin.register(SignInChallenge)
class SignInChallengeAdmin(admin.ModelAdmin):
    list_display = ("nonce", "domain", "expires_at", "consumed_at", "wallet_address")
    readonly_fields = [field.name for field in SignInChallenge._meta.fields]


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "family_id", "expires_at", "revoked_at", "created_at")
    readonly_fields = [field.name for field in RefreshToken._meta.fields]
