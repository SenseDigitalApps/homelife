from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from devices.models import DeviceType
from measurements.models import Measurement


class DiagnosticRule(models.Model):
    class RuleKind(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        WEEKLY = "weekly", "Weekly"

    class FormulaType(models.TextChoices):
        THRESHOLD = "threshold", "Threshold"
        RANGE_SCORE = "range_score", "Range score"
        COMPOSITE_INDEX = "composite_index", "Composite index"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    device_type = models.CharField(max_length=50, choices=DeviceType.choices)
    parameter_type = models.CharField(max_length=50, blank=True, default="")
    rule_kind = models.CharField(max_length=20, choices=RuleKind.choices)
    formula_type = models.CharField(max_length=30, choices=FormulaType.choices)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True, default="")
    summary_template_normal = models.TextField(blank=True, default="")
    summary_template_preventive = models.TextField(blank=True, default="")
    summary_template_critical = models.TextField(blank=True, default="")
    action_template_normal = models.TextField(blank=True, default="")
    action_template_preventive = models.TextField(blank=True, default="")
    action_template_critical = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["device_type", "rule_kind", "parameter_type", "name"]

    def clean(self) -> None:
        if self.rule_kind == self.RuleKind.IMMEDIATE and not self.parameter_type:
            raise ValidationError({"parameter_type": "Immediate rules require parameter_type."})
        if self.rule_kind == self.RuleKind.WEEKLY and self.parameter_type:
            raise ValidationError({"parameter_type": "Weekly rules must not define parameter_type."})

        duplicate_qs = DiagnosticRule.objects.filter(
            device_type=self.device_type,
            parameter_type=self.parameter_type,
            rule_kind=self.rule_kind,
            is_active=True,
        ).exclude(pk=self.pk)
        if self.is_active and duplicate_qs.exists():
            raise ValidationError(
                "Only one active rule is allowed for the same device, parameter and kind."
            )

    def __str__(self) -> str:
        suffix = f" / {self.parameter_type}" if self.parameter_type else ""
        return f"{self.device_type}{suffix} ({self.rule_kind})"


class DiagnosticRuleVariable(models.Model):
    class ValueType(models.TextChoices):
        DECIMAL = "decimal", "Decimal"
        INTEGER = "integer", "Integer"
        PERCENTAGE = "percentage", "Percentage"

    rule = models.ForeignKey(
        DiagnosticRule,
        on_delete=models.CASCADE,
        related_name="variables",
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=120)
    value = models.DecimalField(max_digits=12, decimal_places=4)
    value_type = models.CharField(
        max_length=20,
        choices=ValueType.choices,
        default=ValueType.DECIMAL,
    )
    unit = models.CharField(max_length=20, blank=True, default="")
    min_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    help_text = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["sort_order", "key"]
        unique_together = ("rule", "key")

    def clean(self) -> None:
        if self.min_value is not None and self.value < self.min_value:
            raise ValidationError({"value": "Value is below min_value."})
        if self.max_value is not None and self.value > self.max_value:
            raise ValidationError({"value": "Value is above max_value."})

    def __str__(self) -> str:
        return f"{self.rule.slug}:{self.key}={self.value}"


class Recommendation(models.Model):
    class Engine(models.TextChoices):
        RULES = "rules", "Rules"
        ALGORITHMIC = "algorithmic", "Algorithmic"

    class Level(models.TextChoices):
        NORMAL = "normal", "Normal"
        PREVENTIVE = "preventive", "Preventive"
        CRITICAL = "critical", "Critical"

    class Kind(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        WEEKLY = "weekly", "Weekly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations"
    )
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    device_type = models.CharField(max_length=50, choices=DeviceType.choices, blank=True, default="")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.IMMEDIATE)
    engine = models.CharField(max_length=20, choices=Engine.choices)
    rule = models.ForeignKey(
        DiagnosticRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_outputs",
    )
    rule_version = models.PositiveIntegerField(default=1)
    text = models.TextField()
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.NORMAL)
    metrics_snapshot = models.JSONField(default=dict, blank=True)
    variables_snapshot = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.engine} - {self.level}"


class PeriodicDiagnostic(models.Model):
    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Weekly"

    class Level(models.TextChoices):
        NORMAL = "normal", "Normal"
        PREVENTIVE = "preventive", "Preventive"
        CRITICAL = "critical", "Critical"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="periodic_diagnostics"
    )
    device_type = models.CharField(max_length=50, choices=DeviceType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    frequency = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.WEEKLY)
    rule = models.ForeignKey(
        DiagnosticRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="periodic_diagnostics",
    )
    rule_version = models.PositiveIntegerField(default=1)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.NORMAL)
    score = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    summary = models.TextField()
    recommended_action = models.TextField(blank=True, default="")
    metrics_snapshot = models.JSONField(default=dict, blank=True)
    variables_snapshot = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end", "-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_type", "period_start", "period_end", "frequency"],
                name="unique_periodic_diagnostic_per_user_device_period",
            )
        ]

    def __str__(self) -> str:
        return f"{self.device_type} {self.period_start}..{self.period_end} ({self.level})"
