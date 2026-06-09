from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from devices.models import DeviceType
from measurements.models import Measurement, ParameterType

from .models import DiagnosticRule, PeriodicDiagnostic, Recommendation

logger = logging.getLogger(__name__)
VALID_LEVELS = {"normal", "preventive", "critical"}

DEFAULT_RULES: dict[str, dict[str, object]] = {
    "glucometro:glucose:immediate": {
        "device_type": DeviceType.GLUCOMETRO,
        "parameter_type": ParameterType.GLUCOSE,
        "rule_kind": DiagnosticRule.RuleKind.IMMEDIATE,
        "formula_type": DiagnosticRule.FormulaType.THRESHOLD,
        "summary": {
            "normal": "Glucosa dentro del rango operativo esperado ({value:.2f} {unit}).",
            "preventive": "Glucosa fuera del rango objetivo ({value:.2f} {unit}). Requiere seguimiento.",
            "critical": "Glucosa en rango crítico ({value:.2f} {unit}). Requiere atención prioritaria.",
        },
        "action": {
            "normal": "Mantener seguimiento habitual.",
            "preventive": "Revisar alimentación, adherencia y repetir medición si es necesario.",
            "critical": "Buscar atención médica si el valor persiste o hay síntomas.",
        },
        "variables": [
            ("low_critical", "Hipoglucemia crítica", "54", "integer", "mg/dL", "20", "100"),
            ("low_alert", "Hipoglucemia", "70", "integer", "mg/dL", "40", "120"),
            ("high_alert", "Hiperglucemia", "180", "integer", "mg/dL", "100", "300"),
            ("high_critical", "Hiperglucemia crítica", "250", "integer", "mg/dL", "140", "500"),
            ("weekly_high_pct", "% semanal alto", "0.20", "percentage", "", "0", "1"),
            ("weekly_avg_alert", "Promedio semanal alerta", "140", "integer", "mg/dL", "80", "250"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "glucometro:weekly": {
        "device_type": DeviceType.GLUCOMETRO,
        "parameter_type": "",
        "rule_kind": DiagnosticRule.RuleKind.WEEKLY,
        "formula_type": DiagnosticRule.FormulaType.RANGE_SCORE,
        "summary": {
            "normal": "Resumen semanal de glucosa estable. Promedio {avg_glucose:.2f} {unit}.",
            "preventive": "Resumen semanal de glucosa con excursiones fuera de rango. Promedio {avg_glucose:.2f} {unit}.",
            "critical": "Resumen semanal de glucosa con eventos críticos detectados. Promedio {avg_glucose:.2f} {unit}.",
        },
        "action": {
            "normal": "Mantener monitoreo y hábitos actuales.",
            "preventive": "Revisar patrones de alimentación y control según indicación clínica.",
            "critical": "Priorizar revisión clínica y confirmar lecturas recientes.",
        },
        "variables": [
            ("low_critical", "Hipoglucemia crítica", "54", "integer", "mg/dL", "20", "100"),
            ("low_alert", "Hipoglucemia", "70", "integer", "mg/dL", "40", "120"),
            ("high_alert", "Hiperglucemia", "180", "integer", "mg/dL", "100", "300"),
            ("high_critical", "Hiperglucemia crítica", "250", "integer", "mg/dL", "140", "500"),
            ("weekly_high_pct", "% semanal alto", "0.20", "percentage", "", "0", "1"),
            ("weekly_avg_alert", "Promedio semanal alerta", "140", "integer", "mg/dL", "80", "250"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "oximetro:spo2:immediate": {
        "device_type": DeviceType.OXIMETRO,
        "parameter_type": ParameterType.SPO2,
        "rule_kind": DiagnosticRule.RuleKind.IMMEDIATE,
        "formula_type": DiagnosticRule.FormulaType.THRESHOLD,
        "summary": {
            "normal": "Saturación de oxígeno en rango esperado ({value:.2f} {unit}).",
            "preventive": "Saturación de oxígeno por debajo del rango óptimo ({value:.2f} {unit}).",
            "critical": "Saturación de oxígeno críticamente baja ({value:.2f} {unit}).",
        },
        "action": {
            "normal": "Mantener seguimiento habitual.",
            "preventive": "Repetir medición en reposo y vigilar síntomas.",
            "critical": "Buscar atención clínica urgente si el valor persiste.",
        },
        "variables": [
            ("spo2_normal_min", "SpO2 mínima normal", "95", "integer", "%", "80", "100"),
            ("spo2_warning_min", "SpO2 advertencia", "93", "integer", "%", "70", "100"),
            ("spo2_critical_max", "SpO2 crítica", "92", "integer", "%", "70", "100"),
            ("spo2_emergency_max", "SpO2 emergencia", "89", "integer", "%", "70", "100"),
            ("pulse_normal_min", "Pulso normal mínimo", "60", "integer", "bpm", "20", "120"),
            ("pulse_normal_max", "Pulso normal máximo", "100", "integer", "bpm", "40", "150"),
            ("pulse_critical_low", "Pulso crítico bajo", "50", "integer", "bpm", "20", "80"),
            ("pulse_critical_high", "Pulso crítico alto", "120", "integer", "bpm", "80", "220"),
            ("weekly_low_spo2_count", "Conteo SpO2 baja", "2", "integer", "", "1", "20"),
            ("weekly_high_pulse_pct", "% pulso alto", "0.20", "percentage", "", "0", "1"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "oximetro:pulse_rate:immediate": {
        "device_type": DeviceType.OXIMETRO,
        "parameter_type": ParameterType.PULSE_RATE,
        "rule_kind": DiagnosticRule.RuleKind.IMMEDIATE,
        "formula_type": DiagnosticRule.FormulaType.THRESHOLD,
        "summary": {
            "normal": "Frecuencia de pulso dentro del rango esperado ({value:.2f} {unit}).",
            "preventive": "Frecuencia de pulso fuera del rango habitual ({value:.2f} {unit}).",
            "critical": "Frecuencia de pulso en rango crítico ({value:.2f} {unit}).",
        },
        "action": {
            "normal": "Mantener seguimiento habitual.",
            "preventive": "Repetir medición en reposo y vigilar síntomas.",
            "critical": "Buscar atención médica si el valor persiste o hay síntomas.",
        },
        "variables": [
            ("pulse_normal_min", "Pulso normal mínimo", "60", "integer", "bpm", "20", "120"),
            ("pulse_normal_max", "Pulso normal máximo", "100", "integer", "bpm", "40", "150"),
            ("pulse_critical_low", "Pulso crítico bajo", "50", "integer", "bpm", "20", "80"),
            ("pulse_critical_high", "Pulso crítico alto", "120", "integer", "bpm", "80", "220"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "oximetro:weekly": {
        "device_type": DeviceType.OXIMETRO,
        "parameter_type": "",
        "rule_kind": DiagnosticRule.RuleKind.WEEKLY,
        "formula_type": DiagnosticRule.FormulaType.COMPOSITE_INDEX,
        "summary": {
            "normal": "Resumen semanal de oximetría estable. Promedio SpO2 {avg_spo2:.2f} {spo2_unit}.",
            "preventive": "Resumen semanal de oximetría con valores bajos o pulso alterado. Promedio SpO2 {avg_spo2:.2f} {spo2_unit}.",
            "critical": "Resumen semanal de oximetría con eventos críticos detectados. Promedio SpO2 {avg_spo2:.2f} {spo2_unit}.",
        },
        "action": {
            "normal": "Mantener monitoreo habitual.",
            "preventive": "Repetir mediciones en reposo y revisar tendencia.",
            "critical": "Buscar valoración clínica si persisten lecturas bajas o síntomas.",
        },
        "variables": [
            ("spo2_normal_min", "SpO2 mínima normal", "95", "integer", "%", "80", "100"),
            ("spo2_warning_min", "SpO2 advertencia", "93", "integer", "%", "70", "100"),
            ("spo2_critical_max", "SpO2 crítica", "92", "integer", "%", "70", "100"),
            ("spo2_emergency_max", "SpO2 emergencia", "89", "integer", "%", "70", "100"),
            ("pulse_normal_min", "Pulso normal mínimo", "60", "integer", "bpm", "20", "120"),
            ("pulse_normal_max", "Pulso normal máximo", "100", "integer", "bpm", "40", "150"),
            ("pulse_critical_low", "Pulso crítico bajo", "50", "integer", "bpm", "20", "80"),
            ("pulse_critical_high", "Pulso crítico alto", "120", "integer", "bpm", "80", "220"),
            ("weekly_low_spo2_count", "Conteo SpO2 baja", "2", "integer", "", "1", "20"),
            ("weekly_high_pulse_pct", "% pulso alto", "0.20", "percentage", "", "0", "1"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "tensiometro:bp_systolic:immediate": {
        "device_type": DeviceType.TENSIOMETRO,
        "parameter_type": ParameterType.BP_SYSTOLIC,
        "rule_kind": DiagnosticRule.RuleKind.IMMEDIATE,
        "formula_type": DiagnosticRule.FormulaType.THRESHOLD,
        "summary": {
            "normal": "Presión sistólica en rango esperado ({value:.2f} {unit}).",
            "preventive": "Presión sistólica elevada ({value:.2f} {unit}).",
            "critical": "Presión sistólica críticamente elevada ({value:.2f} {unit}).",
        },
        "action": {
            "normal": "Mantener seguimiento habitual.",
            "preventive": "Repetir medición en reposo y vigilar tendencia.",
            "critical": "Buscar valoración médica prioritaria si persiste.",
        },
        "variables": [
            ("sys_normal_max", "Sistólica normal máxima", "119", "integer", "mmHg", "80", "160"),
            ("sys_elevated_min", "Sistólica elevada", "120", "integer", "mmHg", "80", "180"),
            ("sys_stage1_min", "Sistólica etapa 1", "130", "integer", "mmHg", "90", "220"),
            ("sys_stage2_min", "Sistólica etapa 2", "140", "integer", "mmHg", "100", "240"),
            ("sys_urgent_min", "Sistólica urgencia", "180", "integer", "mmHg", "120", "260"),
            ("dia_normal_max", "Diastólica normal máxima", "79", "integer", "mmHg", "40", "120"),
            ("dia_stage1_min", "Diastólica etapa 1", "80", "integer", "mmHg", "40", "140"),
            ("dia_stage2_min", "Diastólica etapa 2", "90", "integer", "mmHg", "50", "160"),
            ("dia_urgent_min", "Diastólica urgencia", "120", "integer", "mmHg", "60", "180"),
            ("weekly_required_days", "Días requeridos", "2", "integer", "", "1", "7"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "tensiometro:bp_diastolic:immediate": {
        "device_type": DeviceType.TENSIOMETRO,
        "parameter_type": ParameterType.BP_DIASTOLIC,
        "rule_kind": DiagnosticRule.RuleKind.IMMEDIATE,
        "formula_type": DiagnosticRule.FormulaType.THRESHOLD,
        "summary": {
            "normal": "Presión diastólica en rango esperado ({value:.2f} {unit}).",
            "preventive": "Presión diastólica elevada ({value:.2f} {unit}).",
            "critical": "Presión diastólica críticamente elevada ({value:.2f} {unit}).",
        },
        "action": {
            "normal": "Mantener seguimiento habitual.",
            "preventive": "Repetir medición en reposo y vigilar tendencia.",
            "critical": "Buscar valoración médica prioritaria si persiste.",
        },
        "variables": [
            ("sys_normal_max", "Sistólica normal máxima", "119", "integer", "mmHg", "80", "160"),
            ("sys_elevated_min", "Sistólica elevada", "120", "integer", "mmHg", "80", "180"),
            ("sys_stage1_min", "Sistólica etapa 1", "130", "integer", "mmHg", "90", "220"),
            ("sys_stage2_min", "Sistólica etapa 2", "140", "integer", "mmHg", "100", "240"),
            ("sys_urgent_min", "Sistólica urgencia", "180", "integer", "mmHg", "120", "260"),
            ("dia_normal_max", "Diastólica normal máxima", "79", "integer", "mmHg", "40", "120"),
            ("dia_stage1_min", "Diastólica etapa 1", "80", "integer", "mmHg", "40", "140"),
            ("dia_stage2_min", "Diastólica etapa 2", "90", "integer", "mmHg", "50", "160"),
            ("dia_urgent_min", "Diastólica urgencia", "120", "integer", "mmHg", "60", "180"),
            ("weekly_required_days", "Días requeridos", "2", "integer", "", "1", "7"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
    "tensiometro:weekly": {
        "device_type": DeviceType.TENSIOMETRO,
        "parameter_type": "",
        "rule_kind": DiagnosticRule.RuleKind.WEEKLY,
        "formula_type": DiagnosticRule.FormulaType.COMPOSITE_INDEX,
        "summary": {
            "normal": "Resumen semanal de presión arterial estable. Promedio {avg_systolic:.2f}/{avg_diastolic:.2f} mmHg.",
            "preventive": "Resumen semanal de presión arterial con tendencia elevada. Promedio {avg_systolic:.2f}/{avg_diastolic:.2f} mmHg.",
            "critical": "Resumen semanal de presión arterial con eventos críticos detectados. Promedio {avg_systolic:.2f}/{avg_diastolic:.2f} mmHg.",
        },
        "action": {
            "normal": "Mantener monitoreo habitual.",
            "preventive": "Revisar mediciones en reposo y seguir control clínico.",
            "critical": "Buscar valoración clínica prioritaria si la elevación persiste.",
        },
        "variables": [
            ("sys_normal_max", "Sistólica normal máxima", "119", "integer", "mmHg", "80", "160"),
            ("sys_elevated_min", "Sistólica elevada", "120", "integer", "mmHg", "80", "180"),
            ("sys_stage1_min", "Sistólica etapa 1", "130", "integer", "mmHg", "90", "220"),
            ("sys_stage2_min", "Sistólica etapa 2", "140", "integer", "mmHg", "100", "240"),
            ("sys_urgent_min", "Sistólica urgencia", "180", "integer", "mmHg", "120", "260"),
            ("dia_normal_max", "Diastólica normal máxima", "79", "integer", "mmHg", "40", "120"),
            ("dia_stage1_min", "Diastólica etapa 1", "80", "integer", "mmHg", "40", "140"),
            ("dia_stage2_min", "Diastólica etapa 2", "90", "integer", "mmHg", "50", "160"),
            ("dia_urgent_min", "Diastólica urgencia", "120", "integer", "mmHg", "60", "180"),
            ("weekly_required_days", "Días requeridos", "2", "integer", "", "1", "7"),
            ("min_readings_week", "Mínimo lecturas semana", "4", "integer", "", "1", "50"),
        ],
    },
}


@dataclass
class EngineResult:
    engine: str
    text: str
    level: str
    device_type: str
    kind: str = Recommendation.Kind.IMMEDIATE
    rule: DiagnosticRule | None = None
    rule_version: int = 1
    metrics_snapshot: dict[str, object] | None = None
    variables_snapshot: dict[str, object] | None = None


@dataclass
class WeeklyDiagnosticResult:
    level: str
    summary: str
    recommended_action: str
    device_type: str
    rule: DiagnosticRule | None
    rule_version: int
    metrics_snapshot: dict[str, object]
    variables_snapshot: dict[str, object]
    score: Decimal | None = None


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized in VALID_LEVELS:
        return normalized
    return Recommendation.Level.PREVENTIVE


def _device_type_for_parameter(parameter_type: str) -> str:
    mapping = {
        ParameterType.GLUCOSE: DeviceType.GLUCOMETRO,
        ParameterType.SPO2: DeviceType.OXIMETRO,
        ParameterType.PULSE_RATE: DeviceType.OXIMETRO,
        ParameterType.PI_INDEX: DeviceType.OXIMETRO,
        ParameterType.HRV: DeviceType.OXIMETRO,
        ParameterType.BP_SYSTOLIC: DeviceType.TENSIOMETRO,
        ParameterType.BP_DIASTOLIC: DeviceType.TENSIOMETRO,
    }
    return mapping.get(parameter_type, DeviceType.OTRO)


def _measurement_device_type(measurement: Measurement | None, parameter_type: str) -> str:
    if measurement is not None and getattr(measurement, "device_id", None):
        return measurement.device.device_type
    return _device_type_for_parameter(parameter_type)


def _serialize_decimal_dict(data: dict[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value
    return serialized


def _render_template(template: str, context: dict[str, object], fallback: str) -> str:
    if not template:
        return fallback
    safe_context = _serialize_decimal_dict(context)
    try:
        return template.format(**safe_context)
    except Exception:
        logger.warning("Recommendation template rendering failed.", exc_info=True)
        return fallback


def _default_rule_config(device_type: str, parameter_type: str, rule_kind: str) -> dict[str, object]:
    key = f"{device_type}:{parameter_type}:{rule_kind}" if parameter_type else f"{device_type}:{rule_kind}"
    return DEFAULT_RULES[key]


def _resolve_rule(device_type: str, parameter_type: str, rule_kind: str) -> DiagnosticRule | None:
    return (
        DiagnosticRule.objects.filter(
            device_type=device_type,
            parameter_type=parameter_type,
            rule_kind=rule_kind,
            is_active=True,
        )
        .prefetch_related("variables")
        .order_by("-version", "-updated_at")
        .first()
    )


def _rule_variables(rule: DiagnosticRule | None, default_config: dict[str, object]) -> dict[str, Decimal]:
    if rule is not None:
        return {item.key: item.value for item in rule.variables.all()}

    values: dict[str, Decimal] = {}
    for key, _label, value, *_rest in default_config["variables"]:  # type: ignore[index]
        values[key] = _to_decimal(value)
    return values


def _rule_templates(rule: DiagnosticRule | None, default_config: dict[str, object]) -> tuple[dict[str, str], dict[str, str]]:
    default_summary = default_config["summary"]  # type: ignore[index]
    default_action = default_config["action"]  # type: ignore[index]
    if rule is None:
        return default_summary, default_action

    summary_templates = {
        "normal": rule.summary_template_normal or default_summary["normal"],
        "preventive": rule.summary_template_preventive or default_summary["preventive"],
        "critical": rule.summary_template_critical or default_summary["critical"],
    }
    action_templates = {
        "normal": rule.action_template_normal or default_action["normal"],
        "preventive": rule.action_template_preventive or default_action["preventive"],
        "critical": rule.action_template_critical or default_action["critical"],
    }
    return summary_templates, action_templates


def _parameter_label(parameter_type: str) -> str:
    try:
        return Measurement._meta.get_field("parameter_type").choices and ParameterType(parameter_type).label
    except Exception:
        return parameter_type


def _immediate_level_for_parameter(parameter_type: str, value: Decimal, variables: dict[str, Decimal]) -> str:
    if parameter_type == ParameterType.GLUCOSE:
        if value < variables["low_critical"] or value > variables["high_critical"]:
            return Recommendation.Level.CRITICAL
        if value < variables["low_alert"] or value > variables["high_alert"]:
            return Recommendation.Level.PREVENTIVE
        return Recommendation.Level.NORMAL

    if parameter_type == ParameterType.SPO2:
        if value <= variables["spo2_critical_max"]:
            return Recommendation.Level.CRITICAL
        if value < variables["spo2_normal_min"]:
            return Recommendation.Level.PREVENTIVE
        return Recommendation.Level.NORMAL

    if parameter_type == ParameterType.PULSE_RATE:
        if value < variables["pulse_critical_low"] or value > variables["pulse_critical_high"]:
            return Recommendation.Level.CRITICAL
        if value < variables["pulse_normal_min"] or value > variables["pulse_normal_max"]:
            return Recommendation.Level.PREVENTIVE
        return Recommendation.Level.NORMAL

    if parameter_type == ParameterType.BP_SYSTOLIC:
        if value > variables["sys_urgent_min"]:
            return Recommendation.Level.CRITICAL
        if value >= variables["sys_stage1_min"]:
            return Recommendation.Level.PREVENTIVE
        return Recommendation.Level.NORMAL

    if parameter_type == ParameterType.BP_DIASTOLIC:
        if value > variables["dia_urgent_min"]:
            return Recommendation.Level.CRITICAL
        if value >= variables["dia_stage1_min"]:
            return Recommendation.Level.PREVENTIVE
        return Recommendation.Level.NORMAL

    return Recommendation.Level.NORMAL


def generate_immediate_recommendation(
    parameter_type: str | None = None,
    value: Decimal | float | int | None = None,
    unit: str | None = None,
    prefer_ai: bool = False,
    measurement: Measurement | None = None,
) -> EngineResult:
    del prefer_ai
    if measurement is not None:
        parameter_type = measurement.parameter_type
        value = measurement.value
        unit = measurement.unit

    if parameter_type is None or value is None or unit is None:
        raise ValueError("parameter_type, value and unit are required.")

    device_type = _measurement_device_type(measurement, parameter_type)
    try:
        default_config = _default_rule_config(device_type, parameter_type, DiagnosticRule.RuleKind.IMMEDIATE)
    except KeyError:
        numeric_value = _to_decimal(value)
        return EngineResult(
            engine=Recommendation.Engine.ALGORITHMIC,
            text=f"{_parameter_label(parameter_type)} registrado correctamente ({numeric_value:.2f} {unit}).",
            level=Recommendation.Level.NORMAL,
            device_type=device_type,
            metrics_snapshot=_serialize_decimal_dict({"value": numeric_value, "unit": unit}),
            variables_snapshot={},
        )
    rule = _resolve_rule(device_type, parameter_type, DiagnosticRule.RuleKind.IMMEDIATE)
    variables = _rule_variables(rule, default_config)
    summary_templates, action_templates = _rule_templates(rule, default_config)

    numeric_value = _to_decimal(value)
    level = _immediate_level_for_parameter(parameter_type, numeric_value, variables)
    context = {
        "value": numeric_value,
        "unit": unit,
        "parameter_type": parameter_type,
        "parameter_label": _parameter_label(parameter_type),
        "device_type": device_type,
        "action": action_templates[level],
    }
    default_text = f"{_parameter_label(parameter_type)}: {numeric_value:.2f} {unit}."
    text = _render_template(summary_templates[level], context, default_text)

    return EngineResult(
        engine=Recommendation.Engine.ALGORITHMIC,
        text=text,
        level=_normalize_level(level),
        device_type=device_type,
        rule=rule,
        rule_version=rule.version if rule else 1,
        metrics_snapshot=_serialize_decimal_dict({"value": numeric_value, "unit": unit}),
        variables_snapshot=_serialize_decimal_dict(variables),
    )


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values) / Decimal(len(values))


def _percentage(count: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal("0")
    return Decimal(count) / Decimal(total)


def _collect_values(measurements: Iterable[Measurement], parameter_type: str) -> list[Measurement]:
    return [item for item in measurements if item.parameter_type == parameter_type]


def _calculate_weekly_metrics(device_type: str, measurements: Iterable[Measurement]) -> dict[str, object]:
    items = list(measurements)
    if device_type == DeviceType.GLUCOMETRO:
        glucose = [_to_decimal(item.value) for item in _collect_values(items, ParameterType.GLUCOSE)]
        unit = next((item.unit for item in items if item.parameter_type == ParameterType.GLUCOSE), "mg/dL")
        return {
            "reading_count": len(glucose),
            "avg_glucose": _average(glucose),
            "min_glucose": min(glucose) if glucose else Decimal("0"),
            "max_glucose": max(glucose) if glucose else Decimal("0"),
            "pct_lt_70": _percentage(sum(1 for value in glucose if value < Decimal("70")), len(glucose)),
            "pct_lt_54": _percentage(sum(1 for value in glucose if value < Decimal("54")), len(glucose)),
            "pct_gt_180": _percentage(sum(1 for value in glucose if value > Decimal("180")), len(glucose)),
            "pct_gt_250": _percentage(sum(1 for value in glucose if value > Decimal("250")), len(glucose)),
            "unit": unit,
        }

    if device_type == DeviceType.OXIMETRO:
        spo2_items = _collect_values(items, ParameterType.SPO2)
        pulse_items = _collect_values(items, ParameterType.PULSE_RATE)
        spo2_values = [_to_decimal(item.value) for item in spo2_items]
        pulse_values = [_to_decimal(item.value) for item in pulse_items]
        return {
            "reading_count": len(spo2_values) + len(pulse_values),
            "avg_spo2": _average(spo2_values),
            "min_spo2": min(spo2_values) if spo2_values else Decimal("0"),
            "count_spo2_93_94": sum(1 for value in spo2_values if Decimal("93") <= value <= Decimal("94")),
            "count_spo2_le_92": sum(1 for value in spo2_values if value <= Decimal("92")),
            "avg_pulse": _average(pulse_values),
            "pct_pulse_gt_100": _percentage(sum(1 for value in pulse_values if value > Decimal("100")), len(pulse_values)),
            "pct_pulse_gt_120": _percentage(sum(1 for value in pulse_values if value > Decimal("120")), len(pulse_values)),
            "pct_pulse_lt_50": _percentage(sum(1 for value in pulse_values if value < Decimal("50")), len(pulse_values)),
            "spo2_unit": spo2_items[0].unit if spo2_items else "%",
            "pulse_unit": pulse_items[0].unit if pulse_items else "bpm",
        }

    if device_type == DeviceType.TENSIOMETRO:
        systolic_items = _collect_values(items, ParameterType.BP_SYSTOLIC)
        diastolic_items = _collect_values(items, ParameterType.BP_DIASTOLIC)
        systolic_values = [_to_decimal(item.value) for item in systolic_items]
        diastolic_values = [_to_decimal(item.value) for item in diastolic_items]

        daily_stats: dict[date, dict[str, Decimal]] = {}
        for item in items:
            day_key = timezone.localdate(item.measured_at)
            daily_stats.setdefault(day_key, {})
            if item.parameter_type == ParameterType.BP_SYSTOLIC:
                daily_stats[day_key]["sys"] = max(
                    _to_decimal(item.value), daily_stats[day_key].get("sys", Decimal("0"))
                )
            elif item.parameter_type == ParameterType.BP_DIASTOLIC:
                daily_stats[day_key]["dia"] = max(
                    _to_decimal(item.value), daily_stats[day_key].get("dia", Decimal("0"))
                )

        return {
            "reading_count": len(systolic_values) + len(diastolic_values),
            "distinct_days_count": len(daily_stats),
            "avg_systolic": _average(systolic_values),
            "avg_diastolic": _average(diastolic_values),
            "max_systolic": max(systolic_values) if systolic_values else Decimal("0"),
            "max_diastolic": max(diastolic_values) if diastolic_values else Decimal("0"),
            "days_ge_140_90": sum(
                1
                for day in daily_stats.values()
                if day.get("sys", Decimal("0")) >= Decimal("140")
                or day.get("dia", Decimal("0")) >= Decimal("90")
            ),
            "days_ge_130_80": sum(
                1
                for day in daily_stats.values()
                if day.get("sys", Decimal("0")) >= Decimal("130")
                or day.get("dia", Decimal("0")) >= Decimal("80")
            ),
            "count_gt_180_120": sum(
                1 for value in systolic_values if value > Decimal("180")
            )
            + sum(1 for value in diastolic_values if value > Decimal("120")),
        }

    return {"reading_count": 0}


def _classify_weekly(device_type: str, metrics: dict[str, object], variables: dict[str, Decimal]) -> tuple[str, Decimal]:
    if device_type == DeviceType.GLUCOMETRO:
        score = Decimal("0")
        if metrics["pct_lt_54"] > 0 or metrics["pct_gt_250"] >= variables["weekly_high_pct"]:
            return Recommendation.Level.CRITICAL, Decimal("3")
        if (
            metrics["pct_lt_70"] > 0
            or metrics["pct_gt_180"] >= variables["weekly_high_pct"]
            or metrics["avg_glucose"] > variables["weekly_avg_alert"]
        ):
            score += Decimal("2")
            return Recommendation.Level.PREVENTIVE, score
        return Recommendation.Level.NORMAL, score

    if device_type == DeviceType.OXIMETRO:
        score = Decimal("0")
        if metrics["min_spo2"] < variables["spo2_emergency_max"] or metrics["count_spo2_le_92"] >= variables["weekly_low_spo2_count"]:
            return Recommendation.Level.CRITICAL, Decimal("3")
        if (
            metrics["count_spo2_93_94"] >= variables["weekly_low_spo2_count"]
            or metrics["avg_spo2"] < variables["spo2_normal_min"]
            or metrics["avg_pulse"] > variables["pulse_normal_max"]
            or metrics["pct_pulse_gt_100"] >= variables["weekly_high_pulse_pct"]
        ):
            score += Decimal("2")
            if metrics["pct_pulse_gt_120"] > 0 or metrics["pct_pulse_lt_50"] > 0:
                return Recommendation.Level.CRITICAL, Decimal("3")
            return Recommendation.Level.PREVENTIVE, score
        return Recommendation.Level.NORMAL, score

    if device_type == DeviceType.TENSIOMETRO:
        score = Decimal("0")
        if metrics["count_gt_180_120"] > 0:
            return Recommendation.Level.CRITICAL, Decimal("3")
        if (
            metrics["days_ge_140_90"] >= int(variables["weekly_required_days"])
            or metrics["avg_systolic"] >= variables["sys_stage1_min"]
            or metrics["avg_diastolic"] >= variables["dia_stage1_min"]
        ):
            score += Decimal("2")
            return Recommendation.Level.PREVENTIVE, score
        return Recommendation.Level.NORMAL, score

    return Recommendation.Level.NORMAL, Decimal("0")


def generate_weekly_diagnostic(
    *,
    user: object,
    device_type: str,
    measurements: Iterable[Measurement],
    period_start: date,
    period_end: date,
) -> WeeklyDiagnosticResult | None:
    default_config = _default_rule_config(device_type, "", DiagnosticRule.RuleKind.WEEKLY)
    rule = _resolve_rule(device_type, "", DiagnosticRule.RuleKind.WEEKLY)
    variables = _rule_variables(rule, default_config)
    summary_templates, action_templates = _rule_templates(rule, default_config)
    metrics = _calculate_weekly_metrics(device_type, measurements)
    reading_count = int(metrics.get("reading_count", 0))
    if reading_count < int(variables.get("min_readings_week", Decimal("4"))):
        return None

    level, score = _classify_weekly(device_type, metrics, variables)
    context = {
        **metrics,
        "device_type": device_type,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
    fallback_summary = f"Resumen semanal para {device_type} entre {period_start} y {period_end}."
    fallback_action = "Mantener seguimiento clínico habitual."
    summary = _render_template(summary_templates[level], context, fallback_summary)
    action = _render_template(action_templates[level], context, fallback_action)
    return WeeklyDiagnosticResult(
        level=_normalize_level(level),
        summary=summary,
        recommended_action=action,
        device_type=device_type,
        rule=rule,
        rule_version=rule.version if rule else 1,
        metrics_snapshot=_serialize_decimal_dict(metrics),
        variables_snapshot=_serialize_decimal_dict(variables),
        score=score,
    )


def build_recommendation_payload(
    user_id: int,
    result: EngineResult,
    measurement_id: int | None = None,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "measurement_id": measurement_id,
        "device_type": result.device_type,
        "kind": result.kind,
        "engine": result.engine,
        "rule": result.rule,
        "rule_version": result.rule_version,
        "text": result.text,
        "level": _normalize_level(result.level),
        "metrics_snapshot": result.metrics_snapshot or {},
        "variables_snapshot": result.variables_snapshot or {},
    }


def _week_bounds(reference_date: date | None = None) -> tuple[date, date]:
    end = reference_date or timezone.now().date()
    start = end - timedelta(days=6)
    return start, end


def generate_weekly_diagnostics_for_period(
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[PeriodicDiagnostic]:
    resolved_start, resolved_end = _week_bounds(period_end)
    if period_start is not None:
        resolved_start = period_start
    if period_end is not None:
        resolved_end = period_end

    period_start_dt = timezone.make_aware(datetime.combine(resolved_start, time.min))
    period_end_dt = timezone.make_aware(datetime.combine(resolved_end, time.max))

    created: list[PeriodicDiagnostic] = []
    with transaction.atomic():
        user_model = get_user_model()
        users = user_model.objects.filter(
            measurements__measured_at__gte=period_start_dt,
            measurements__measured_at__lte=period_end_dt,
        ).distinct()
        for user in users:
            for device_type in (
                DeviceType.GLUCOMETRO,
                DeviceType.OXIMETRO,
                DeviceType.TENSIOMETRO,
            ):
                measurements = list(
                    Measurement.objects.filter(
                        user=user,
                        device__device_type=device_type,
                        measured_at__gte=period_start_dt,
                        measured_at__lte=period_end_dt,
                    ).select_related("device")
                )
                if not measurements:
                    continue
                result = generate_weekly_diagnostic(
                    user=user,
                    device_type=device_type,
                    measurements=measurements,
                    period_start=resolved_start,
                    period_end=resolved_end,
                )
                if result is None:
                    continue
                diagnostic, was_created = PeriodicDiagnostic.objects.get_or_create(
                    user=user,
                    device_type=device_type,
                    period_start=resolved_start,
                    period_end=resolved_end,
                    frequency=PeriodicDiagnostic.Frequency.WEEKLY,
                    defaults={
                        "rule": result.rule,
                        "rule_version": result.rule_version,
                        "level": result.level,
                        "score": result.score,
                        "summary": result.summary,
                        "recommended_action": result.recommended_action,
                        "metrics_snapshot": result.metrics_snapshot,
                        "variables_snapshot": result.variables_snapshot,
                    },
                )
                if was_created:
                    created.append(diagnostic)
    return created
