from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions

from .models import PeriodicDiagnostic, Recommendation
from .serializers import PeriodicDiagnosticSerializer, RecommendationSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["recommendations"],
        responses={
            200: RecommendationSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
)
class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recommendation.objects.filter(user=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["recommendations"],
        responses={
            200: PeriodicDiagnosticSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
)
class WeeklyDiagnosticListView(generics.ListAPIView):
    serializer_class = PeriodicDiagnosticSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = PeriodicDiagnostic.objects.filter(user=self.request.user)
        device_type = self.request.query_params.get("device_type")
        level = self.request.query_params.get("level")
        if device_type:
            queryset = queryset.filter(device_type=device_type)
        if level:
            queryset = queryset.filter(level=level)
        return queryset
