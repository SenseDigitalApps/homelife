from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("id", "user", "date_from", "date_to", "file_url", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("date_from must be before or equal to date_to.")
        return attrs
