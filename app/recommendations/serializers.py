from rest_framework import serializers

from .models import DiagnosticRule, DiagnosticRuleVariable, PeriodicDiagnostic, Recommendation


class DiagnosticRuleVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticRuleVariable
        fields = (
            "id",
            "key",
            "label",
            "value",
            "value_type",
            "unit",
            "min_value",
            "max_value",
            "sort_order",
            "help_text",
        )


class DiagnosticRuleSerializer(serializers.ModelSerializer):
    variables = DiagnosticRuleVariableSerializer(many=True, read_only=True)

    class Meta:
        model = DiagnosticRule
        fields = (
            "id",
            "name",
            "slug",
            "device_type",
            "parameter_type",
            "rule_kind",
            "formula_type",
            "is_active",
            "version",
            "description",
            "variables",
        )


class RecommendationSerializer(serializers.ModelSerializer):
    rule = DiagnosticRuleSerializer(read_only=True)

    class Meta:
        model = Recommendation
        fields = (
            "id",
            "user",
            "measurement",
            "device_type",
            "kind",
            "engine",
            "rule",
            "rule_version",
            "text",
            "level",
            "metrics_snapshot",
            "variables_snapshot",
            "generated_at",
        )
        read_only_fields = ("id", "user", "generated_at")


class PeriodicDiagnosticSerializer(serializers.ModelSerializer):
    rule = DiagnosticRuleSerializer(read_only=True)

    class Meta:
        model = PeriodicDiagnostic
        fields = (
            "id",
            "user",
            "device_type",
            "period_start",
            "period_end",
            "frequency",
            "rule",
            "rule_version",
            "level",
            "score",
            "summary",
            "recommended_action",
            "metrics_snapshot",
            "variables_snapshot",
            "generated_at",
        )
        read_only_fields = ("id", "user", "generated_at")
