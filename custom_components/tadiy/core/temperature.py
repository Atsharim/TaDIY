"""Temperature sensor fusion for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

OUTLIER_THRESHOLD: float = 10.0
MIN_VALID_TEMP: float = -20.0
MAX_VALID_TEMP: float = 50.0


@dataclass
class SensorReading:
    """A temperature sensor reading with metadata."""

    entity_id: str
    temperature: float
    weight: float = 1.0
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Validate sensor reading."""
        if not MIN_VALID_TEMP <= self.temperature <= MAX_VALID_TEMP:
            raise ValueError(
                f"Temperature {self.temperature}°C out of valid range "
                f"({MIN_VALID_TEMP}°C to {MAX_VALID_TEMP}°C)"
            )
        if self.weight <= 0:
            raise ValueError(f"Weight must be positive, got {self.weight}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "temperature": self.temperature,
            "weight": self.weight,
            "timestamp": self.timestamp,
        }


def calculate_fused_temperature(
    readings: list[SensorReading],
    outlier_detection: bool = True,
) -> float | None:
    """
    Calculate fused temperature from multiple sensors using weighted average.

    Args:
        readings: List of sensor readings
        outlier_detection: Enable outlier detection and removal

    Returns:
        Fused temperature or None if no valid readings
    """
    if not readings:
        _LOGGER.warning("No sensor readings provided")
        return None

    valid_readings = [
        r for r in readings if MIN_VALID_TEMP <= r.temperature <= MAX_VALID_TEMP
    ]

    if not valid_readings:
        _LOGGER.warning("No valid temperature readings")
        return None

    if outlier_detection and len(valid_readings) > 2:
        valid_readings = _remove_outliers(valid_readings)

    if not valid_readings:
        _LOGGER.warning("All readings were outliers")
        return None

    total_weighted_temp = sum(r.temperature * r.weight for r in valid_readings)
    total_weight = sum(r.weight for r in valid_readings)

    if total_weight == 0:
        _LOGGER.error("Total weight is zero")
        return None

    fused_temp = total_weighted_temp / total_weight

    _LOGGER.debug(
        "Fused temperature: %.2f°C from %d sensors (weights: %s)",
        fused_temp,
        len(valid_readings),
        [f"{r.weight:.1f}" for r in valid_readings],
    )

    return round(fused_temp, 2)


def _remove_outliers(readings: list[SensorReading]) -> list[SensorReading]:
    """
    Remove outlier readings using median absolute deviation.

    Args:
        readings: List of sensor readings

    Returns:
        Filtered list without outliers
    """
    if len(readings) <= 2:
        return readings

    temps = [r.temperature for r in readings]
    median = sorted(temps)[len(temps) // 2]

    filtered = [r for r in readings if abs(r.temperature - median) <= OUTLIER_THRESHOLD]

    if len(filtered) < len(readings):
        removed = len(readings) - len(filtered)
        _LOGGER.debug(
            "Removed %d outlier reading(s) (median: %.2f°C, threshold: %.1f°C)",
            removed,
            median,
            OUTLIER_THRESHOLD,
        )

    return filtered if filtered else readings


def calculate_weighted_average_history(
    readings: list[SensorReading],
    alpha: float = 0.3,
) -> float | None:
    """
    Calculate exponentially weighted moving average.

    Args:
        readings: List of historical sensor readings (newest first)
        alpha: Smoothing factor (0-1), higher = more weight on recent values

    Returns:
        Smoothed temperature or None
    """
    if not readings:
        return None

    if not 0 < alpha <= 1:
        raise ValueError(f"Alpha must be between 0 and 1, got {alpha}")

    result = readings[0].temperature
    for i, reading in enumerate(readings[1:], start=1):
        weight = (1 - alpha) ** i
        result += reading.temperature * weight

    return round(result, 2)
