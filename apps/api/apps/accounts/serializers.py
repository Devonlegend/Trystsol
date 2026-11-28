from rest_framework import serializers


class VerifySIWSRequest(serializers.Serializer):
    message = serializers.CharField(max_length=4096, trim_whitespace=False)
    signature = serializers.JSONField()

    def validate_signature(self, value):
        if not isinstance(value, (str, list)):
            raise serializers.ValidationError("Signature must be base64 or a byte array.")
        if isinstance(value, list) and not all(isinstance(item, int) and 0 <= item <= 255 for item in value):
            raise serializers.ValidationError("Signature byte array values must be 0-255.")
        return value


class RefreshRequest(serializers.Serializer):
    refresh = serializers.CharField(
        max_length=512, trim_whitespace=False, required=False, allow_blank=True
    )


class LogoutRequest(serializers.Serializer):
    refresh = serializers.CharField(
        max_length=512, trim_whitespace=False, required=False, allow_blank=True
    )
