import re

from rest_framework import serializers

HEX32_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class Hex32Field(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not HEX32_RE.match(value):
            raise serializers.ValidationError("Expected 32 bytes encoded as 64 hex characters.")
        return value.lower()


class RoadmapCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    order = serializers.IntegerField(min_value=0, max_value=1000, default=0)


class RoadmapUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    order = serializers.IntegerField(min_value=0, max_value=1000, required=False)


class MilestoneCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=200)
    description = serializers.CharField(min_length=20, max_length=5000)
    deadline = serializers.DateField()
    required_approvals = serializers.IntegerField(min_value=2, max_value=5, default=2)
    criteria_id = serializers.UUIDField()
    roadmap_id = serializers.UUIDField(required=False, allow_null=True)


class AssignReviewersSerializer(serializers.Serializer):
    reviewer_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=5
    )
    required_approvals = serializers.IntegerField(min_value=1, max_value=5)


def validate_http_url(value: str) -> str:
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator

    try:
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError as exc:
        raise serializers.ValidationError("URI must be an http(s) URL.") from exc
    return value


class EvidenceInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["repo", "document", "url", "file"])
    uri = serializers.CharField(min_length=1, max_length=2048)
    sha256 = Hex32Field()
    content_type = serializers.CharField(required=False, allow_blank=True, max_length=128)
    size_bytes = serializers.IntegerField(min_value=0, max_value=25 * 1024 * 1024, default=0)

    def validate_uri(self, value):
        return validate_http_url(value)


class SubmitMilestoneSerializer(serializers.Serializer):
    evidence = EvidenceInputSerializer(many=True, min_length=1, max_length=10)

    def validate_evidence(self, value):
        primary_uri = value[0]["uri"]
        if len(primary_uri.encode("utf-8")) > 128:
            raise serializers.ValidationError(
                "The first evidence URI is written on-chain and must be at most 128 bytes."
            )
        return value


class CriteriaCreateSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    criteria_hash = Hex32Field()
    criteria_uri = serializers.CharField(min_length=1, max_length=128)

    def validate_criteria_uri(self, value):
        return validate_http_url(value)


class ReviewerVerdictSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["verify", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)
