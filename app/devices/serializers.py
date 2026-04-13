from rest_framework import serializers

from .models import Device, DeviceProfile


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id",
            "user",
            "device_type",
            "serial",
            "protocol",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")


class DeviceProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceProfile
        fields = (
            "id",
            "name",
            "device_type",
            "manufacturer",
            "model_name",
            "protocol",
            "ble_service_uuid",
            "ble_notify_characteristic_uuid",
            "ble_write_characteristic_uuid",
            "ble_characteristic_uuid",
            "supported_parameters",
            "is_active",
        )
