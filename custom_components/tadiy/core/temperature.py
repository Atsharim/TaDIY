"""Temperature sensor fusion for TaDIY."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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


# Comfort Index Constants (Thermal Comfort Standard)
COMFORT_TEMP_IDEAL = 21.0
COMFORT_TEMP_MIN = 20.0
COMFORT_TEMP_MAX = 22.0
COMFORT_TEMP_ACCEPTABLE_MIN = 19.0
COMFORT_TEMP_ACCEPTABLE_MAX = 23.0
COMFORT_HUMIDITY_IDEAL = 50.0
COMFORT_HUMIDITY_MIN = 40.0
COMFORT_HUMIDITY_MAX = 60.0
COMFORT_HUMIDITY_ACCEPTABLE_MIN = 35.0
COMFORT_HUMIDITY_ACCEPTABLE_MAX = 65.0
COMFORT_TEMP_COLD = 17.0
COMFORT_TEMP_WARM = 25.0
COMFORT_HUMIDITY_DRY = 30.0
COMFORT_HUMIDITY_WET = 70.0


def calculate_comfort(
    temperature: float | None, humidity: float | None
) -> dict[str, Any]:
    """Calculate room comfort level, score, and color with refined scoring."""
    if temperature is None:
        return {
            "comfort_level": "unknown",
            "comfort_score": 0,
            "comfort_color": "#9E9E9E",
            "temperature": None,
            "humidity": None,
            "comfort_position": {"x": 50, "y": 50},
        }

    # Temperature score (0-100): Gaussian-like curve centered at ideal temp
    temp_diff = abs(temperature - COMFORT_TEMP_IDEAL)

    if temp_diff <= 0.5:  # Within ±0.5°C of ideal
        temp_score = 100.0
    elif COMFORT_TEMP_MIN <= temperature <= COMFORT_TEMP_MAX:
        # Good zone: 85-99%
        temp_score = 100.0 - (temp_diff * 15.0)  # Max 1.5°C diff = 22.5 penalty
    elif COMFORT_TEMP_ACCEPTABLE_MIN <= temperature <= COMFORT_TEMP_ACCEPTABLE_MAX:
        # Acceptable zone: 60-84%
        if temperature < COMFORT_TEMP_MIN:
            temp_score = 85.0 - (COMFORT_TEMP_MIN - temperature) * 25.0
        else:
            temp_score = 85.0 - (temperature - COMFORT_TEMP_MAX) * 25.0
    elif temperature < COMFORT_TEMP_COLD:
        # Poor - too cold
        temp_score = max(0.0, 60.0 - (COMFORT_TEMP_COLD - temperature) * 15.0)
    elif temperature > COMFORT_TEMP_WARM:
        # Poor - too warm
        temp_score = max(0.0, 60.0 - (temperature - COMFORT_TEMP_WARM) * 15.0)
    elif temperature < COMFORT_TEMP_ACCEPTABLE_MIN:
        temp_score = 60.0 - (COMFORT_TEMP_ACCEPTABLE_MIN - temperature) * 20.0
    else:  # temperature > COMFORT_TEMP_ACCEPTABLE_MAX
        temp_score = 60.0 - (temperature - COMFORT_TEMP_ACCEPTABLE_MAX) * 20.0

    # Humidity score (0-100): Similar refined approach
    if humidity is not None:
        hum_diff = abs(humidity - COMFORT_HUMIDITY_IDEAL)

        if hum_diff <= 2.5:  # Within ±2.5% of ideal
            hum_score = 100.0
        elif COMFORT_HUMIDITY_MIN <= humidity <= COMFORT_HUMIDITY_MAX:
            # Good zone: 85-99%
            hum_score = 100.0 - (hum_diff * 3.0)
        elif (
            COMFORT_HUMIDITY_ACCEPTABLE_MIN
            <= humidity
            <= COMFORT_HUMIDITY_ACCEPTABLE_MAX
        ):
            # Acceptable zone: 60-84%
            if humidity < COMFORT_HUMIDITY_MIN:
                hum_score = 85.0 - (COMFORT_HUMIDITY_MIN - humidity) * 5.0
            else:
                hum_score = 85.0 - (humidity - COMFORT_HUMIDITY_MAX) * 5.0
        elif humidity < COMFORT_HUMIDITY_DRY:
            hum_score = max(0.0, 60.0 - (COMFORT_HUMIDITY_DRY - humidity) * 4.0)
        elif humidity > COMFORT_HUMIDITY_WET:
            hum_score = max(0.0, 60.0 - (humidity - COMFORT_HUMIDITY_WET) * 4.0)
        elif humidity < COMFORT_HUMIDITY_ACCEPTABLE_MIN:
            hum_score = 60.0 - (COMFORT_HUMIDITY_ACCEPTABLE_MIN - humidity) * 3.0
        else:  # humidity > COMFORT_HUMIDITY_ACCEPTABLE_MAX
            hum_score = 60.0 - (humidity - COMFORT_HUMIDITY_ACCEPTABLE_MAX) * 3.0

        # Combined score: 60% temperature, 40% humidity
        score = round(temp_score * 0.6 + hum_score * 0.4)
    else:
        hum_score = None
        score = round(temp_score)

    # Determine primary comfort level
    if score >= 80:
        level = "optimal"
        color = "#4CAF50"  # green
    elif temperature > COMFORT_TEMP_WARM:
        level = "too_warm"
        color = "#FF9800"  # orange
    elif temperature < COMFORT_TEMP_COLD:
        level = "too_cold"
        color = "#2196F3"  # blue
    elif humidity is not None and humidity < COMFORT_HUMIDITY_DRY:
        level = "too_dry"
        color = "#FFC107"  # amber
    elif humidity is not None and humidity > COMFORT_HUMIDITY_WET:
        level = "too_humid"
        color = "#9C27B0"  # purple
    else:
        level = "moderate"
        color = "#8BC34A"  # light green

    # Position on a circle indicator (x: humidity axis, y: temperature axis)
    pos_x = 50
    if humidity is not None:
        pos_x = max(0, min(100, int((humidity - 20) / 60 * 100)))
    pos_y = max(0, min(100, int((30 - temperature) / 20 * 100)))

    return {
        "comfort_level": level,
        "comfort_score": max(0, min(100, score)),
        "comfort_color": color,
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1) if humidity is not None else None,
        "comfort_position": {"x": pos_x, "y": pos_y},
        "temp_score": round(temp_score, 1),
        "humidity_score": round(hum_score, 1) if hum_score is not None else None,
    }
