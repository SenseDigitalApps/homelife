from django.db import OperationalError, connection
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    tags=["system"],
    responses=inline_serializer(
        name="HealthResponse",
        fields={
            "status": serializers.CharField(),
            "service": serializers.CharField(),
            "version": serializers.CharField(),
            "db": serializers.CharField(),
        },
    ),
    examples=[
        OpenApiExample(
            "Healthy response",
            value={"status": "ok", "service": "medsync-api", "version": "0.1.0", "db": "ok"},
            response_only=True,
        )
    ],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    db_status = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        db_status = "fail"

    return Response(
        {
            "status": "ok",
            "service": "medsync-api",
            "version": "0.1.0",
            "db": db_status,
        }
    )
