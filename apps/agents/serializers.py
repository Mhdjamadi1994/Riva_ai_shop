from rest_framework import serializers

from .models import AdminReport


class AdminReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminReport
        fields = ("id", "status", "findings", "summary", "error", "created_at", "started_at", "completed_at")
        read_only_fields = fields
