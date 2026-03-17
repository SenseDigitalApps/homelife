from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions

from .models import Report
from .serializers import ReportSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["reports"],
        responses={
            200: ReportSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
    post=extend_schema(
        tags=["reports"],
        responses={
            201: ReportSerializer,
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
)
class ReportListCreateView(generics.ListCreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
