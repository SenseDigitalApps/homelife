from django.conf import settings
from django.db import models


class Device(models.Model):
    class Protocol(models.TextChoices):
        BLUETOOTH = "bluetooth", "Bluetooth"
        WIFI = "wifi", "WiFi"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices"
    )
    device_type = models.CharField(max_length=50)
    serial = models.CharField(max_length=120, unique=True)
    protocol = models.CharField(max_length=20, choices=Protocol.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.device_type} ({self.serial})"
