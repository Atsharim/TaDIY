"""Sensor management logic for TaDIY."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

_LOGGER = logging.getLogger(__package__)

TRV_SENSOR_WEIGHT = 0.3


class SensorReading(NamedTuple):
    """Container for temperature sensor readings."""

    entity_id: str
    temperature: float
    weight: float = 1.0


def calculate_fused_temperature(readings: list[SensorReading]) -> float | None:
    """Calculate weighted average temperature from multiple sensors."""
    if not readings:
        return None

    total_weight = sum(r.weight for r in readings)
    if total_weight == 0:
        return None

    weighted_sum = sum(r.temperature * r.weight for r in readings)
    return round(weighted_sum / total_weight, 2)


class SensorManager:
    """Handles sensor data reading and fusion for a room."""

    def __init__(self, coordinator: Any) -> None:
        """Initialize the sensor manager."""
        self.coordinator = coordinator
        self.hass = coordinator.hass

    def _debug(self, message: str, *args: Any) -> None:
        """Log sensor debug message using coordinator's logger."""
        if hasattr(self.coordinator, "debug"):
            self.coordinator.debug("sensors", message, *args)

    def get_fused_temperature(self) -> float | None:
        """Get the current room temperature from available sensors."""
        config = self.coordinator.room_config

        # Try main sensor first
        main_temp = self._get_sensor_value(config.main_temp_sensor_id)
        if main_temp is not None:
            self._debug(
                "Temperature: MAIN SENSOR %s = %.2f",
                config.main_temp_sensor_id,
                main_temp,
            )
            return main_temp

        # Fallback to TRVs
        trv_readings = []
        for trv_id in config.trv_entity_ids:
            state = self.hass.states.get(trv_id)
            if state:
                try:
                    current = state.attributes.get("current_temperature")
                    if current is not None:
                        reading = SensorReading(
                            entity_id=trv_id,
                            temperature=float(current),
                            weight=TRV_SENSOR_WEIGHT,
                        )
                        trv_readings.append(reading)
                        self._debug(
                            "TRV sensor %s = %.2f (weight: %.1f)",
                            trv_id,
                            float(current),
                            TRV_SENSOR_WEIGHT,
                        )
                except (ValueError, TypeError):
                    self._debug("TRV sensor %s: invalid value", trv_id)
                    continue

        if trv_readings:
            fused = calculate_fused_temperature(trv_readings)
            self._debug(
                "Temperature: FUSED from %d TRV(s) = %.2f",
                len(trv_readings),
                fused or 0,
            )
            return fused

        self._debug("Temperature: NO SENSORS AVAILABLE")
        return None

    def get_outdoor_temperature(self) -> float | None:
        """Get current outdoor temperature."""
        config = self.coordinator.room_config

        # Try room-level outdoor sensor first
        outdoor_temp = self._get_sensor_value(config.outdoor_sensor_id)
        if outdoor_temp is not None:
            self._debug(
                "Outdoor: ROOM SENSOR %s = %.1f",
                config.outdoor_sensor_id,
                outdoor_temp,
            )
            return outdoor_temp

        # Fallback to hub's weather entity
        if self.coordinator.hub_coordinator:
            from ..const import CONF_WEATHER_ENTITY

            weather_entity = self.coordinator.hub_coordinator.config_data.get(
                CONF_WEATHER_ENTITY
            )
            if weather_entity:
                state = self.hass.states.get(weather_entity)
                if state:
                    try:
                        outdoor_temp = float(state.attributes.get("temperature"))
                        self._debug(
                            "Outdoor: WEATHER ENTITY %s = %.1f",
                            weather_entity,
                            outdoor_temp,
                        )
                        return outdoor_temp
                    except (ValueError, TypeError):
                        self._debug(
                            "Outdoor: WEATHER ENTITY %s - invalid value",
                            weather_entity,
                        )

        self._debug("Outdoor: NOT AVAILABLE")
        return None

    def get_humidity(self) -> float | None:
        """Get current room humidity."""
        config = self.coordinator.room_config
        humidity = self._get_sensor_value(config.humidity_sensor_id)

        if humidity is not None:
            self._debug(
                "Humidity: %s = %.1f%%",
                config.humidity_sensor_id,
                humidity,
            )

        return humidity

    def is_window_open(self) -> bool:
        """Check if any window is open."""
        window_ids = self.coordinator.room_config.window_sensor_ids
        if not window_ids:
            return False

        for entity_id in window_ids:
            state = self.hass.states.get(entity_id)
            if state and state.state == "on":
                self._debug("Window: %s is OPEN", entity_id)
                return True

        return False

    def _get_sensor_value(self, entity_id: str | None) -> float | None:
        """Get numeric value from sensor."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None
