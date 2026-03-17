from django.conf import settings
from django.db import models

from devices.models import Device


class Measurement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="measurements"
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="measurements")
    parameter_type = models.CharField(max_length=50)
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
