from rest_framework import serializers

from .models import Measurement


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = (
            "id",
            "user",
            "device",
            "parameter_type",
            "value",
            "unit",
            "measured_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")
