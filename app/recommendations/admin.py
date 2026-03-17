from django.contrib import admin

from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "engine", "level", "generated_at")
    list_filter = ("engine", "level", "generated_at")
    search_fields = ("user__username", "user__email", "text")
