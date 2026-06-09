from django.contrib import admin

from .models import DiagnosticRule, DiagnosticRuleVariable, PeriodicDiagnostic, Recommendation


class DiagnosticRuleVariableInline(admin.TabularInline):
    model = DiagnosticRuleVariable
    extra = 0
    ordering = ("sort_order", "key")


@admin.register(DiagnosticRule)
class DiagnosticRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "device_type", "parameter_type", "rule_kind", "formula_type", "is_active", "version")
    list_filter = ("device_type", "rule_kind", "formula_type", "is_active")
    search_fields = ("name", "slug", "description")
    inlines = [DiagnosticRuleVariableInline]


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_type", "kind", "engine", "level", "generated_at")
    list_filter = ("device_type", "kind", "engine", "level", "generated_at")
    search_fields = ("user__username", "user__email", "text")


@admin.register(PeriodicDiagnostic)
class PeriodicDiagnosticAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_type", "frequency", "level", "period_start", "period_end", "generated_at")
    list_filter = ("device_type", "frequency", "level", "period_start", "period_end")
    search_fields = ("user__username", "user__email", "summary", "recommended_action")
