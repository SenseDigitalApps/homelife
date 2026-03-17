import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers

from devices.models import Device
from recommendations.engines import (
    build_recommendation_payload,
    generate_immediate_recommendation,
)
from recommendations.models import Recommendation

from .models import Measurement
from .serializers import MeasurementSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        tags=["measurements"],
        responses={
            200: MeasurementSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
    post=extend_schema(
        tags=["measurements"],
        responses={
            201: MeasurementSerializer,
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
        },
    ),
)
class MeasurementListCreateView(generics.ListCreateAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Measurement.objects.filter(user=self.request.user)
        from_value = self.request.query_params.get("from")
        to_value = self.request.query_params.get("to")
        device = self.request.query_params.get("device")
        parameter = self.request.query_params.get("parameter")

        if from_value:
            queryset = queryset.filter(measured_at__gte=from_value)
        if to_value:
            queryset = queryset.filter(measured_at__lte=to_value)
        if device:
            queryset = queryset.filter(device_id=device)
        if parameter:
            queryset = queryset.filter(parameter_type=parameter)
        return queryset

    def perform_create(self, serializer):
        device: Device = serializer.validated_data["device"]
        if device.user_id != self.request.user.id:
            raise serializers.ValidationError(
                {"device": "Device does not belong to the authenticated user."}
            )
        measurement = serializer.save(user=self.request.user)

        try:
            result = generate_immediate_recommendation(
                parameter_type=measurement.parameter_type,
                value=measurement.value,
                unit=measurement.unit,
                prefer_ai=True,
            )
            payload = build_recommendation_payload(
                user_id=self.request.user.id,
                result=result,
                measurement_id=measurement.id,
            )
            Recommendation.objects.create(**payload)
        except Exception:
            # Recommendation generation must not block measurement intake.
            logger.exception("Recommendation generation failed for measurement_id=%s", measurement.id)
