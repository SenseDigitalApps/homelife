from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            "birth_date",
            "biological_sex",
            "initial_weight_kg",
            "height_cm",
            "activity_level",
            "preexisting_conditions",
        )


class RegisterSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password", "profile")
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        profile_data = validated_data.pop("profile", None)
        user_model = get_user_model()
        user = user_model.objects.create_user(**validated_data)
        if profile_data:
            Profile.objects.create(user=user, **profile_data)
        else:
            Profile.objects.create(user=user)
        return user


class RegisterResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
