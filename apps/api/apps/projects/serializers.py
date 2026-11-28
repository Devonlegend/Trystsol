from rest_framework import serializers

from .models import Project


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=120)
    description = serializers.CharField(min_length=20, max_length=5000)
    website = serializers.URLField(required=False, allow_blank=True, max_length=200)
    category_slug = serializers.SlugField(required=False, allow_blank=True, max_length=64)


class ProjectDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class FounderProfileSerializer(serializers.Serializer):
    display_name = serializers.CharField(min_length=2, max_length=120)
    bio = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    website = serializers.URLField(required=False, allow_blank=True)


class ProjectSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "website",
            "application_status",
            "lifecycle_status",
            "data_origin",
            "onchain_project_pda",
            "chain_signature",
            "chain_slot",
            "created_at",
        ]


class TokenMintSerializer(serializers.Serializer):
    token_mint = serializers.CharField(allow_blank=True, max_length=44)

    def validate_token_mint(self, value):
        if not value:
            return value
        from apps.accounts.siws import SIWSError, b58decode

        try:
            if len(b58decode(value)) != 32:
                raise SIWSError("Address is not 32 bytes.")
        except SIWSError as exc:
            raise serializers.ValidationError("Enter a valid base58 Solana mint.") from exc
        return value
