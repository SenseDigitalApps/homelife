from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions

from .models import Device
from .serializers import DeviceSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["devices"],
        responses={
            200: DeviceSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
    post=extend_schema(
        tags=["devices"],
        responses={201: DeviceSerializer, 401: OpenApiResponse(description="Unauthorized")},
    ),
)
class DeviceListCreateView(generics.ListCreateAPIView):
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
