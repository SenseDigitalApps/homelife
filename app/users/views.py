from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    EmailOrUsernameTokenObtainPairSerializer,
    LogoutSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
)


@extend_schema_view(
    post=extend_schema(
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer, 400: RegisterResponseSerializer},
        tags=["auth"],
    )
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"detail": "User registered successfully."}, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


@extend_schema_view(
    post=extend_schema(
        request=LogoutSerializer,
        responses={
            205: RegisterResponseSerializer,
            400: OpenApiResponse(description="Invalid refresh token"),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=["auth"],
    )
)
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as exc:
            raise serializers.ValidationError({"refresh": "Invalid refresh token."}) from exc
        return Response({"detail": "Logout successful."}, status=status.HTTP_205_RESET_CONTENT)
