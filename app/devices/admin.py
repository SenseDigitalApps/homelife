from django.contrib import admin

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_type", "serial", "protocol", "is_active", "created_at")
    list_filter = ("protocol", "is_active", "created_at")
    search_fields = ("serial", "device_type", "user__username", "user__email")
