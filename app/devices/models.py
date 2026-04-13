from django.conf import settings
from django.db import models


class DeviceType(models.TextChoices):
    GLUCOMETRO = "glucometro", "Glucómetro"
    OXIMETRO = "oximetro", "Oxímetro"
    TENSIOMETRO = "tensiometro", "Tensiómetro"
    TERMOMETRO = "termometro", "Termómetro"
    ECG = "ecg", "ECG"
    OTRO = "otro", "Otro"


class Device(models.Model):
    class Protocol(models.TextChoices):
        BLUETOOTH = "bluetooth", "Bluetooth"
        WIFI = "wifi", "WiFi"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices"
    )
    device_type = models.CharField(max_length=50, choices=DeviceType.choices)
    serial = models.CharField(max_length=120, unique=True)
    protocol = models.CharField(max_length=20, choices=Protocol.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.device_type} ({self.serial})"


class DeviceProfile(models.Model):
    name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices)
    manufacturer = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    protocol = models.CharField(max_length=20, choices=Device.Protocol.choices)
    ble_service_uuid = models.CharField(max_length=64, blank=True, default="")
    ble_notify_characteristic_uuid = models.CharField(max_length=64, blank=True, default="")
    ble_write_characteristic_uuid = models.CharField(max_length=64, blank=True, default="")
    ble_characteristic_uuid = models.CharField(max_length=64, blank=True, default="")
    supported_parameters = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["device_type", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.model_name})"
