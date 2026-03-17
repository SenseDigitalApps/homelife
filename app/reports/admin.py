from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date_from", "date_to", "created_at")
    list_filter = ("created_at", "date_from", "date_to")
    search_fields = ("user__username", "user__email", "file_url")
