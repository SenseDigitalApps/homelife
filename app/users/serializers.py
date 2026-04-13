from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD

        identifier = (attrs.get(username_field) or "").strip()
        email = (attrs.get("email") or "").strip()

        if email:
            identifier = email

        if identifier and "@" in identifier:
            candidates = user_model.objects.filter(email__iexact=identifier).order_by("id")
            count = candidates.count()
            if count == 1:
                attrs[username_field] = getattr(candidates.first(), username_field)
            elif count > 1:
                raise serializers.ValidationError(
                    {"email": "Multiple accounts match this email. Please login with username."}
                )

        return super().validate(attrs)
