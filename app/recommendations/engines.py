from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import Iterable, Protocol

logger = logging.getLogger(__name__)
VALID_LEVELS = {"normal", "preventive", "critical"}


@dataclass
class EngineResult:
    engine: str
    text: str
    level: str


class RecommendationEngine(Protocol):
    def generate_immediate(
        self, parameter_type: str, value: Decimal | float | int, unit: str
    ) -> EngineResult: ...

    def generate_consolidated(
        self,
        parameter_type: str,
        values: list[Decimal | float | int],
        unit: str,
        days: int,
    ) -> EngineResult: ...


def _to_decimal(value: Decimal | float | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized in VALID_LEVELS:
        return normalized
    return "preventive"


class RulesEngine:
    engine_name = "rules"

    def generate_immediate(
        self, parameter_type: str, value: Decimal | float | int, unit: str
    ) -> EngineResult:
        numeric_value = _to_decimal(value)
        level, message = self._classify(
            parameter_type=parameter_type, value=numeric_value, unit=unit
        )
        return EngineResult(
            engine=self.engine_name,
            text=message,
            level=_normalize_level(level),
        )

    def generate_consolidated(
        self,
        parameter_type: str,
        values: list[Decimal | float | int],
        unit: str,
        days: int,
    ) -> EngineResult:
        if not values:
            return EngineResult(
                engine=self.engine_name,
                text=f"No measurements available for {parameter_type} in the last {days} days.",
                level="normal",
            )

        numeric_values = [_to_decimal(item) for item in values]
        average = sum(numeric_values) / Decimal(len(numeric_values))
        level, base_message = self._classify(
            parameter_type=parameter_type, value=average, unit=unit
        )
        return EngineResult(
            engine=self.engine_name,
            level=_normalize_level(level),
            text=f"{base_message} Consolidated trend over {days} days: average {average:.2f} {unit}.",
        )

    def _classify(self, parameter_type: str, value: Decimal, unit: str) -> tuple[str, str]:
        key = parameter_type.strip().lower()

        if key == "glucose":
            if value >= Decimal("180"):
                return (
                    "critical",
                    f"Glucose is high ({value:.2f} {unit}). Seek medical guidance if persistent.",
                )
            if value >= Decimal("126"):
                return (
                    "preventive",
                    f"Glucose is elevated ({value:.2f} {unit}). Monitor and review lifestyle.",
                )
            return "normal", f"Glucose is within expected range ({value:.2f} {unit})."

        if key == "spo2":
            if value < Decimal("90"):
                return (
                    "critical",
                    f"SpO2 is low ({value:.2f} {unit}). Seek immediate clinical attention.",
                )
            if value < Decimal("95"):
                return (
                    "preventive",
                    f"SpO2 is below optimal ({value:.2f} {unit}). Keep monitoring closely.",
                )
            return "normal", f"SpO2 is in a normal range ({value:.2f} {unit})."

        if key == "temp":
            if value >= Decimal("39"):
                return (
                    "critical",
                    f"Temperature is very high ({value:.2f} {unit}). Consider urgent evaluation.",
                )
            if value >= Decimal("37.5"):
                return (
                    "preventive",
                    f"Temperature is slightly elevated ({value:.2f} {unit}). Observe symptoms.",
                )
            return "normal", f"Temperature is within normal range ({value:.2f} {unit})."

        if key == "bp_systolic":
            if value >= Decimal("180"):
                return "critical", f"Systolic blood pressure is critical ({value:.2f} {unit})."
            if value >= Decimal("140"):
                return "preventive", f"Systolic blood pressure is elevated ({value:.2f} {unit})."
            return "normal", f"Systolic blood pressure is in expected range ({value:.2f} {unit})."

        if value > Decimal("0"):
            return "normal", f"{parameter_type} recorded successfully ({value:.2f} {unit})."
        return (
            "preventive",
            f"{parameter_type} value looks unusual ({value:.2f} {unit}). Verify device reading.",
        )


class AIEngine:
    engine_name = "ai"

    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def is_enabled(self) -> bool:
        return bool(self.openai_api_key or self.gemini_api_key)

    def generate_immediate(
        self, parameter_type: str, value: Decimal | float | int, unit: str
    ) -> EngineResult:
        if not self.is_enabled:
            raise RuntimeError("AI engine is disabled because no API key is configured.")
        # Hook only: no external provider call in this step.
        numeric_value = _to_decimal(value)
        return EngineResult(
            engine=self.engine_name,
            level="preventive",
            text=f"AI hook ready for {parameter_type}. Current reading: {numeric_value:.2f} {unit}.",
        )

    def generate_consolidated(
        self,
        parameter_type: str,
        values: list[Decimal | float | int],
        unit: str,
        days: int,
    ) -> EngineResult:
        if not self.is_enabled:
            raise RuntimeError("AI engine is disabled because no API key is configured.")
        # Hook only: no external provider call in this step.
        return EngineResult(
            engine=self.engine_name,
            level="preventive",
            text=f"AI consolidated hook ready for {parameter_type} over {days} days ({len(values)} points, unit {unit}).",
        )


def get_engine(prefer_ai: bool = True) -> RecommendationEngine:
    if prefer_ai:
        ai_engine = AIEngine()
        if ai_engine.is_enabled:
            return ai_engine
    return RulesEngine()


def generate_immediate_recommendation(
    parameter_type: str,
    value: Decimal | float | int,
    unit: str,
    prefer_ai: bool = True,
) -> EngineResult:
    engine = get_engine(prefer_ai=prefer_ai)
    try:
        result = engine.generate_immediate(parameter_type=parameter_type, value=value, unit=unit)
        result.level = _normalize_level(result.level)
        return result
    except Exception:
        logger.warning("AI immediate recommendation failed, fallback to rules.", exc_info=True)
        return RulesEngine().generate_immediate(
            parameter_type=parameter_type, value=value, unit=unit
        )


def generate_consolidated_recommendation(
    parameter_type: str,
    values: list[Decimal | float | int],
    unit: str,
    days: int,
    prefer_ai: bool = True,
) -> EngineResult:
    engine = get_engine(prefer_ai=prefer_ai)
    try:
        result = engine.generate_consolidated(
            parameter_type=parameter_type, values=values, unit=unit, days=days
        )
        result.level = _normalize_level(result.level)
        return result
    except Exception:
        logger.warning("AI consolidated recommendation failed, fallback to rules.", exc_info=True)
        return RulesEngine().generate_consolidated(
            parameter_type=parameter_type, values=values, unit=unit, days=days
        )


def generate_consolidated_from_measurements(
    parameter_type: str,
    measurements: Iterable[object],
    days: int,
    prefer_ai: bool = True,
) -> EngineResult:
    values: list[Decimal | float | int] = []
    unit = ""
    for measurement in measurements:
        if getattr(measurement, "parameter_type", "").strip().lower() != parameter_type.strip().lower():
            continue
        values.append(getattr(measurement, "value"))
        if not unit:
            unit = str(getattr(measurement, "unit", ""))

    if not unit:
        unit = "unit"

    return generate_consolidated_recommendation(
        parameter_type=parameter_type,
        values=values,
        unit=unit,
        days=days,
        prefer_ai=prefer_ai,
    )


def build_recommendation_payload(
    user_id: int,
    result: EngineResult,
    measurement_id: int | None = None,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "measurement_id": measurement_id,
        "engine": result.engine,
        "text": result.text,
        "level": _normalize_level(result.level),
    }
