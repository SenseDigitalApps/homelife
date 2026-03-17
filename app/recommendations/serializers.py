from rest_framework import serializers

from .models import Recommendation


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ("id", "user", "measurement", "engine", "text", "level", "generated_at")
        read_only_fields = ("id", "user", "generated_at")
