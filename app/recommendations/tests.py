from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import PropertyMock, patch

from django.test import TestCase

from .engines import (
    AIEngine,
    RulesEngine,
    generate_consolidated_from_measurements,
    generate_consolidated_recommendation,
    generate_immediate_recommendation,
)


@dataclass
class _MeasurementStub:
    parameter_type: str
    value: Decimal
    unit: str


class RecommendationEnginesTests(TestCase):
    def test_rules_engine_immediate_glucose_levels(self):
        rules = RulesEngine()
        critical = rules.generate_immediate("glucose", 185, "mg/dL")
        preventive = rules.generate_immediate("glucose", 130, "mg/dL")
        normal = rules.generate_immediate("glucose", 100, "mg/dL")

        self.assertEqual(critical.level, "critical")
        self.assertEqual(preventive.level, "preventive")
        self.assertEqual(normal.level, "normal")

    def test_immediate_fallback_when_ai_raises(self):
        with patch.object(AIEngine, "is_enabled", new_callable=PropertyMock, return_value=True):
            with patch.object(AIEngine, "generate_immediate", side_effect=RuntimeError("provider timeout")):
                result = generate_immediate_recommendation("glucose", 140, "mg/dL", prefer_ai=True)

        self.assertEqual(result.engine, "rules")
        self.assertIn(result.level, {"normal", "preventive", "critical"})

    def test_consolidated_recommendation_output_is_valid(self):
        result = generate_consolidated_recommendation(
            parameter_type="glucose",
            values=[95, 125, 145],
            unit="mg/dL",
            days=7,
            prefer_ai=False,
        )
        self.assertEqual(result.engine, "rules")
        self.assertIn("Consolidated trend over 7 days", result.text)
        self.assertIn(result.level, {"normal", "preventive", "critical"})

    def test_consolidated_from_measurements_filters_parameter(self):
        measurements = [
            _MeasurementStub(parameter_type="glucose", value=Decimal("100"), unit="mg/dL"),
            _MeasurementStub(parameter_type="spo2", value=Decimal("96"), unit="%"),
            _MeasurementStub(parameter_type="glucose", value=Decimal("160"), unit="mg/dL"),
        ]
        result = generate_consolidated_from_measurements(
            parameter_type="glucose",
            measurements=measurements,
            days=15,
            prefer_ai=False,
        )
        self.assertEqual(result.engine, "rules")
        self.assertIn("15 days", result.text)
