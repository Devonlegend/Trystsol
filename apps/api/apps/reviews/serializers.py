from rest_framework import serializers


class ReviewerCreateSerializer(serializers.Serializer):
    wallet_address = serializers.CharField(min_length=32, max_length=44)


class DisputeCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=20, max_length=4000)


class DisputeResolveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["upheld", "rejected"])
    resolution = serializers.CharField(min_length=5, max_length=4000)
