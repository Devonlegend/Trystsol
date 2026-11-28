from rest_framework import serializers


class GitHubChallengeRequest(serializers.Serializer):
    project_id = serializers.UUIDField()
    repo_url = serializers.URLField(max_length=300)


class GitHubVerifyRequest(serializers.Serializer):
    challenge_id = serializers.UUIDField()
