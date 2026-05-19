from decimal import Decimal

from rest_framework import serializers

from .models import Measurement, ParameterType

PHYSIOLOGICAL_RANGES = {
    "glucose": (Decimal("20"), Decimal("600")),
    "weight": (Decimal("20"), Decimal("220")),
    "impedance": (Decimal("200"), Decimal("1100")),
    "body_fat_pct": (Decimal("1"), Decimal("75")),
    "body_water_pct": (Decimal("20"), Decimal("80")),
    "muscle_mass": (Decimal("10"), Decimal("120")),
    "bmi": (Decimal("10"), Decimal("70")),
    "bmr": (Decimal("500"), Decimal("4000")),
    "visceral_fat": (Decimal("1"), Decimal("59")),
    "spo2": (Decimal("70"), Decimal("100")),
    "pulse_rate": (Decimal("20"), Decimal("250")),
    "pi_index": (Decimal("0.1"), Decimal("20")),
    "hrv": (Decimal("1"), Decimal("300")),
    "bp_systolic": (Decimal("60"), Decimal("260")),
    "bp_diastolic": (Decimal("30"), Decimal("160")),
}


def validate_physiological_range(parameter_type, value):
    bounds = PHYSIOLOGICAL_RANGES.get(parameter_type)
    if bounds is None:
        return
    low, high = bounds
    if value < low or value > high:
        raise serializers.ValidationError(
            {
                "value": (
                    f"Valor fuera de rango fisiologico para '{parameter_type}'. "
                    f"Rango valido: {low}-{high}. Recibido: {value}"
                )
            }
        )


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = (
            "id",
            "user",
            "device",
            "parameter_type",
            "value",
            "unit",
            "measured_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate(self, attrs):
        validate_physiological_range(attrs.get("parameter_type", ""), attrs.get("value", Decimal("0")))
        return attrs


class ReadingItemSerializer(serializers.Serializer):
    parameter_type = serializers.ChoiceField(choices=ParameterType.choices)
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit = serializers.CharField(max_length=20)

    def validate(self, attrs):
        validate_physiological_range(attrs["parameter_type"], attrs["value"])
        return attrs


class MeasurementBatchSerializer(serializers.Serializer):
    device = serializers.PrimaryKeyRelatedField(
        queryset=Measurement._meta.get_field("device").related_model.objects.all()
    )
    measured_at = serializers.DateTimeField()
    readings = ReadingItemSerializer(many=True, min_length=1)
