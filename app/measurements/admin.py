from django.contrib import admin

from .models import Measurement


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device", "parameter_type", "value", "unit", "measured_at")
    list_filter = ("parameter_type", "unit", "measured_at")
    search_fields = ("user__username", "user__email", "device__serial", "parameter_type")
