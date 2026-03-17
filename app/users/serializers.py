from django.contrib.auth import get_user_model
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password")
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        user_model = get_user_model()
        return user_model.objects.create_user(**validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
