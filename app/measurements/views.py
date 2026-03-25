import logging

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device, DeviceProfile
from recommendations.engines import (
    build_recommendation_payload,
    generate_immediate_recommendation,
)
from recommendations.models import Recommendation

from .models import Measurement
from .serializers import MeasurementBatchSerializer, MeasurementSerializer

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

        profile = DeviceProfile.objects.filter(
            device_type=device.device_type,
            is_active=True,
        ).first()
        if profile and profile.supported_parameters:
            param = serializer.validated_data["parameter_type"]
            if param not in profile.supported_parameters:
                raise serializers.ValidationError(
                    {
                        "parameter_type": (
                            f"El parámetro '{param}' no es compatible con un dispositivo "
                            f"de tipo '{device.device_type}'. "
                            f"Parámetros soportados: {', '.join(profile.supported_parameters)}"
                        )
                    }
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
            logger.exception("Recommendation generation failed for measurement_id=%s", measurement.id)


@extend_schema(
    tags=["measurements"],
    request=MeasurementBatchSerializer,
    responses={
        201: MeasurementSerializer(many=True),
        400: OpenApiResponse(description="Bad Request"),
        401: OpenApiResponse(description="Unauthorized"),
    },
)
class MeasurementBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        batch_serializer = MeasurementBatchSerializer(data=request.data)
        batch_serializer.is_valid(raise_exception=True)

        device = batch_serializer.validated_data["device"]
        measured_at = batch_serializer.validated_data["measured_at"]
        readings = batch_serializer.validated_data["readings"]

        if device.user_id != request.user.id:
            raise serializers.ValidationError(
                {"device": "Device does not belong to the authenticated user."}
            )

        profile = DeviceProfile.objects.filter(
            device_type=device.device_type,
            is_active=True,
        ).first()
        if profile and profile.supported_parameters:
            for reading in readings:
                if reading["parameter_type"] not in profile.supported_parameters:
                    raise serializers.ValidationError(
                        {
                            "parameter_type": (
                                f"El parámetro '{reading['parameter_type']}' no es compatible "
                                f"con un dispositivo de tipo '{device.device_type}'. "
                                f"Parámetros soportados: {', '.join(profile.supported_parameters)}"
                            )
                        }
                    )

        created_measurements = []
        with transaction.atomic():
            for reading in readings:
                measurement = Measurement.objects.create(
                    user=request.user,
                    device=device,
                    parameter_type=reading["parameter_type"],
                    value=reading["value"],
                    unit=reading["unit"],
                    measured_at=measured_at,
                )
                created_measurements.append(measurement)

        for measurement in created_measurements:
            try:
                result = generate_immediate_recommendation(
                    parameter_type=measurement.parameter_type,
                    value=measurement.value,
                    unit=measurement.unit,
                    prefer_ai=True,
                )
                payload = build_recommendation_payload(
                    user_id=request.user.id,
                    result=result,
                    measurement_id=measurement.id,
                )
                Recommendation.objects.create(**payload)
            except Exception:
                logger.exception(
                    "Recommendation generation failed for measurement_id=%s", measurement.id
                )

        output = MeasurementSerializer(created_measurements, many=True)
        return Response(output.data, status=status.HTTP_201_CREATED)
