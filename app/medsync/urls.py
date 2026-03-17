from django.contrib import admin
from django.urls import path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.health import health_check
from devices.views import DeviceListCreateView
from measurements.views import MeasurementListCreateView
from recommendations.views import RecommendationListView
from reports.views import ReportListCreateView
from users.views import LoginView, LogoutView, RefreshView, RegisterView


@extend_schema(
    tags=["system"],
    responses=inline_serializer(
        name="WelcomeResponse",
        fields={"message": serializers.CharField()},
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def welcome(request):
    return Response({"message": "Welcome to MedSync API"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", welcome, name="welcome"),
    path("health/", health_check, name="health"),
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/devices/", DeviceListCreateView.as_view(), name="devices-list-create"),
    path("api/measurements/", MeasurementListCreateView.as_view(), name="measurements-list-create"),
    path("api/reports/", ReportListCreateView.as_view(), name="reports-list-create"),
    path("api/recommendations/", RecommendationListView.as_view(), name="recommendations-list"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
]
