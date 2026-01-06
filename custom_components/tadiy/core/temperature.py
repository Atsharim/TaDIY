"""Temperature and sensor fusion logic for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class SensorReading:
    """Single sensor reading with optional humidity."""
    
    entity_id: str
    temperature: float
    weight: float = 1.0
    humidity: float | None = None


def calculate_fused_temperature(
    readings: Iterable[SensorReading],
    use_humidity_compensation: bool = False,
) -> float | None:
    """Calculate weighted average temperature with optional humidity compensation.
    
    Args:
        readings: List of sensor readings with weights
        use_humidity_compensation: If True, adjust perceived temperature based on humidity
        
    Returns:
        Fused temperature value or None if no valid readings
    """
    readings = list(readings)
    if not readings:
        return None

    # Filter invalid values
    valid_readings = [r for r in readings if r.temperature > -50 and r.temperature < 100]
    if not valid_readings:
        return None

    total_weight = sum(r.weight for r in valid_readings)
    if total_weight == 0:
        return None

    # Weighted average
    weighted_sum = sum(r.temperature * r.weight for r in valid_readings)
    fused_temp = weighted_sum / total_weight

    # Optional: Humidity-based adjustment (perceived temperature)
    if use_humidity_compensation:
        fused_temp = apply_humidity_compensation(fused_temp, valid_readings)

    return round(fused_temp, 1)


def apply_humidity_compensation(
    temperature: float,
    readings: list[SensorReading],
) -> float:
    """Apply humidity compensation to perceived temperature.
    
    High humidity makes it feel warmer, low humidity cooler.
    Formula: Adjusted = Temp + ((Humidity - 50) * 0.02)
    
    Args:
        temperature: Base temperature
        readings: Sensor readings with humidity data
        
    Returns:
        Adjusted temperature
    """
    readings_with_humidity = [r for r in readings if r.humidity is not None]
    if not readings_with_humidity:
        return temperature

    # Average humidity
    avg_humidity = sum(r.humidity for r in readings_with_humidity) / len(readings_with_humidity)

    # Compensation: +/- max 1°C at extreme values
    # 50% Humidity = neutral
    # 70% = +0.4°C perceived
    # 30% = -0.4°C perceived
    compensation = (avg_humidity - 50) * 0.02
    
    return temperature + compensation


def calculate_temperature_trend(
    current: float,
    previous: float,
    time_delta_minutes: float,
) -> float:
    """Calculate temperature change rate in °C per hour.
    
    Args:
        current: Current temperature
        previous: Previous temperature
        time_delta_minutes: Time between measurements in minutes
        
    Returns:
        Temperature change rate (°C/h), positive = heating, negative = cooling
    """
    if time_delta_minutes <= 0:
        return 0.0

    temp_diff = current - previous
    rate_per_hour = (temp_diff / time_delta_minutes) * 60

    return round(rate_per_hour, 2)


def estimate_time_to_target(
    current_temp: float,
    target_temp: float,
    heating_rate: float,
) -> int:
    """Estimate time in minutes to reach target temperature.
    
    Args:
        current_temp: Current temperature
        target_temp: Target temperature
        heating_rate: Known heating rate in °C/h
        
    Returns:
        Estimated minutes to target, or 0 if already reached/invalid
    """
    if heating_rate <= 0 or target_temp <= current_temp:
        return 0

    temp_diff = target_temp - current_temp
    hours_needed = temp_diff / heating_rate
    minutes_needed = int(hours_needed * 60)

    return max(0, minutes_needed)
