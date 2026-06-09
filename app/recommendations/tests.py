from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from devices.models import Device
from measurements.models import Measurement

from .engines import (
    DEFAULT_RULES,
    generate_immediate_recommendation,
    generate_weekly_diagnostic,
    generate_weekly_diagnostics_for_period,
)
from .models import DiagnosticRule, DiagnosticRuleVariable, PeriodicDiagnostic, Recommendation


class RecommendationEnginesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="engine_user",
            password="StrongPass123!",
            email="engine@example.com",
        )

    def _create_device(self, device_type: str, serial: str) -> Device:
        return Device.objects.create(
            user=self.user,
            device_type=device_type,
            serial=serial,
            protocol=Device.Protocol.BLUETOOTH,
            is_active=True,
        )

    def test_immediate_glucose_levels_follow_algorithmic_thresholds(self):
        device = self._create_device("glucometro", "GLU-001")
        low = Measurement(
            user=self.user,
            device=device,
            parameter_type="glucose",
            value=Decimal("50"),
            unit="mg/dL",
            measured_at=timezone.now(),
        )
        alert = Measurement(
            user=self.user,
            device=device,
            parameter_type="glucose",
            value=Decimal("190"),
            unit="mg/dL",
            measured_at=timezone.now(),
        )
        normal = Measurement(
            user=self.user,
            device=device,
            parameter_type="glucose",
            value=Decimal("100"),
            unit="mg/dL",
            measured_at=timezone.now(),
        )

        self.assertEqual(generate_immediate_recommendation(measurement=low).level, "critical")
        self.assertEqual(generate_immediate_recommendation(measurement=alert).level, "preventive")
        self.assertEqual(generate_immediate_recommendation(measurement=normal).level, "normal")

    def test_configurable_rule_variable_changes_result(self):
        device = self._create_device("glucometro", "GLU-002")
        rule = DiagnosticRule.objects.create(
            name="Glucosa inmediata personalizada",
            slug="glucose-immediate-custom",
            device_type="glucometro",
            parameter_type="glucose",
            rule_kind=DiagnosticRule.RuleKind.IMMEDIATE,
            formula_type=DiagnosticRule.FormulaType.THRESHOLD,
            summary_template_normal="ok",
            summary_template_preventive="alerta",
            summary_template_critical="critico",
        )
        default_config = DEFAULT_RULES["glucometro:glucose:immediate"]
        for idx, (key, label, value, value_type, unit, min_value, max_value) in enumerate(
            default_config["variables"]
        ):
            if key == "high_alert":
                value = "150"
            DiagnosticRuleVariable.objects.create(
                rule=rule,
                key=key,
                label=label,
                value=Decimal(str(value)),
                value_type=value_type,
                unit=unit,
                min_value=Decimal(str(min_value)),
                max_value=Decimal(str(max_value)),
                sort_order=idx,
            )

        measurement = Measurement(
            user=self.user,
            device=device,
            parameter_type="glucose",
            value=Decimal("160"),
            unit="mg/dL",
            measured_at=timezone.now(),
        )
        result = generate_immediate_recommendation(measurement=measurement)
        self.assertEqual(result.level, "preventive")
        self.assertEqual(result.rule, rule)
        self.assertEqual(result.engine, Recommendation.Engine.ALGORITHMIC)

    def test_generate_weekly_diagnostic_for_glucose(self):
        device = self._create_device("glucometro", "GLU-003")
        base = timezone.now() - timedelta(days=2)
        for idx, value in enumerate([100, 120, 210, 260, 80]):
            Measurement.objects.create(
                user=self.user,
                device=device,
                parameter_type="glucose",
                value=Decimal(str(value)),
                unit="mg/dL",
                measured_at=base + timedelta(hours=idx),
            )

        measurements = list(Measurement.objects.filter(user=self.user, device=device))
        result = generate_weekly_diagnostic(
            user=self.user,
            device_type="glucometro",
            measurements=measurements,
            period_start=(timezone.now() - timedelta(days=6)).date(),
            period_end=timezone.now().date(),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.level, "critical")
        self.assertIn("avg_glucose", result.metrics_snapshot)

    def test_weekly_generation_is_idempotent(self):
        device = self._create_device("tensiometro", "BP-001")
        now = timezone.now()
        for day_offset, sys_value, dia_value in [
            (0, 145, 92),
            (1, 150, 95),
            (2, 138, 88),
        ]:
            measured_at = now - timedelta(days=day_offset)
            Measurement.objects.create(
                user=self.user,
                device=device,
                parameter_type="bp_systolic",
                value=Decimal(str(sys_value)),
                unit="mmHg",
                measured_at=measured_at,
            )
            Measurement.objects.create(
                user=self.user,
                device=device,
                parameter_type="bp_diastolic",
                value=Decimal(str(dia_value)),
                unit="mmHg",
                measured_at=measured_at,
            )

        first = generate_weekly_diagnostics_for_period(period_end=now.date())
        second = generate_weekly_diagnostics_for_period(period_end=now.date())
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        self.assertEqual(PeriodicDiagnostic.objects.filter(user=self.user, device_type="tensiometro").count(), 1)

    def test_management_command_generates_weekly_diagnostics(self):
        device = self._create_device("oximetro", "OX-001")
        now = timezone.now()
        for day_offset, spo2, pulse in [
            (0, 96, 78),
            (1, 94, 82),
            (2, 91, 130),
        ]:
            measured_at = now - timedelta(days=day_offset)
            Measurement.objects.create(
                user=self.user,
                device=device,
                parameter_type="spo2",
                value=Decimal(str(spo2)),
                unit="%",
                measured_at=measured_at,
            )
            Measurement.objects.create(
                user=self.user,
                device=device,
                parameter_type="pulse_rate",
                value=Decimal(str(pulse)),
                unit="bpm",
                measured_at=measured_at,
            )

        call_command("generate_weekly_diagnostics", period_end=now.date())
        diagnostic = PeriodicDiagnostic.objects.get(user=self.user, device_type="oximetro")
        self.assertEqual(diagnostic.frequency, "weekly")
        self.assertIn(diagnostic.level, {"preventive", "critical"})
