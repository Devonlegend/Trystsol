from rest_framework import serializers


class ConfirmIntentRequest(serializers.Serializer):
    signature = serializers.CharField(max_length=88, trim_whitespace=True)


class ProjectSnapshot(serializers.Serializer):
    pda = serializers.CharField(max_length=44)
    lifecycle_status = serializers.ChoiceField(choices=["active", "completed", "suspended"])


class MilestoneSnapshot(serializers.Serializer):
    pda = serializers.CharField(max_length=44)
    status = serializers.ChoiceField(
        choices=["pending", "submitted", "under_review", "verified", "rejected"]
    )
    round = serializers.IntegerField(min_value=0)
    approvals = serializers.IntegerField(min_value=0)
    rejections = serializers.IntegerField(min_value=0)


class IndexerIngestRequest(serializers.Serializer):
    cursor_name = serializers.CharField(max_length=64, default="main")
    signature = serializers.CharField(max_length=88)
    slot = serializers.IntegerField(min_value=0)
    block_time = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    projects = ProjectSnapshot(many=True, required=False, default=list)
    milestones = MilestoneSnapshot(many=True, required=False, default=list)
