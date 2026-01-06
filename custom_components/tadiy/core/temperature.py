"""Temperature and sensor fusion logic for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class SensorReading:
    """Single sensor reading."""
    entity_id: str
    temperature: float
    weight: float = 1.0


def calculate_fused_temperature(readings: Iterable[SensorReading]) -> float | None:
    """Return weighted average temperature for given readings.

    Placeholder implementation, will be extended later.
    """
    readings = list(readings)
    if not readings:
        return None

    total_weight = sum(r.weight for r in readings)
    if total_weight == 0:
        return None

    return sum(r.temperature * r.weight for r in readings) / total_weight
