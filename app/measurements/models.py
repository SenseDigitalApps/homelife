from django.conf import settings
from django.db import models

from devices.models import Device


class ParameterType(models.TextChoices):
    GLUCOSE = "glucose", "Glucosa"
    WEIGHT = "weight", "Peso"
    IMPEDANCE = "impedance", "Impedancia"
    BODY_FAT_PCT = "body_fat_pct", "Grasa corporal %"
    BODY_WATER_PCT = "body_water_pct", "Agua corporal %"
    MUSCLE_MASS = "muscle_mass", "Masa muscular"
    BMI = "bmi", "Índice de masa corporal"
    BMR = "bmr", "Metabolismo basal"
    VISCERAL_FAT = "visceral_fat", "Grasa visceral"
    SPO2 = "spo2", "SpO2"
    PULSE_RATE = "pulse_rate", "Frecuencia de pulso"
    PI_INDEX = "pi_index", "Índice de perfusión"
    HRV = "hrv", "Variabilidad de frecuencia cardíaca"
    BP_SYSTOLIC = "bp_systolic", "Presión sistólica"
    BP_DIASTOLIC = "bp_diastolic", "Presión diastólica"
    TEMP = "temp", "Temperatura"
    OTRO = "otro", "Otro"


class Measurement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="measurements"
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="measurements")
    parameter_type = models.CharField(max_length=50, choices=ParameterType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20)
    measured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-measured_at"]
        indexes = [
            models.Index(fields=["user", "measured_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.parameter_type}: {self.value} {self.unit}"
