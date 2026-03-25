from django.contrib import admin

from .models import Device, DeviceProfile


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_type", "serial", "protocol", "is_active", "created_at")
    list_filter = ("protocol", "is_active", "created_at")
    search_fields = ("serial", "device_type", "user__username", "user__email")


@admin.register(DeviceProfile)
class DeviceProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "device_type",
        "manufacturer",
        "model_name",
        "protocol",
        "is_active",
    )
    list_filter = ("device_type", "protocol", "is_active")
    search_fields = ("name", "manufacturer", "model_name")
