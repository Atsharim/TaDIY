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

    def get_fused_temperature(self) -> float | None:
        """Get the current room temperature from available sensors."""
        config = self.coordinator.room_config
        
        main_temp = self._get_sensor_value(config.main_temp_sensor_id)
        if main_temp is not None:
            return main_temp
            
        # Fallback to TRVs
        trv_readings = []
        for trv_id in config.trv_entity_ids:
            state = self.hass.states.get(trv_id)
            if state:
                try:
                    current = state.attributes.get("current_temperature")
                    if current is not None:
                        trv_readings.append(
                            SensorReading(
                                entity_id=trv_id,
                                temperature=float(current),
                                weight=TRV_SENSOR_WEIGHT
                            )
                        )
                except (ValueError, TypeError):
                    continue
        
        return calculate_fused_temperature(trv_readings)

    def get_outdoor_temperature(self) -> float | None:
        """Get current outdoor temperature."""
        config = self.coordinator.room_config
        outdoor_temp = self._get_sensor_value(config.outdoor_sensor_id)
        
        if outdoor_temp is None and self.coordinator.hub_coordinator:
            # Fallback to hub's weather entity
            from ..const import CONF_WEATHER_ENTITY
            weather_entity = self.coordinator.hub_coordinator.config_data.get(CONF_WEATHER_ENTITY)
            if weather_entity:
                state = self.hass.states.get(weather_entity)
                if state:
                    try:
                        outdoor_temp = float(state.attributes.get("temperature"))
                    except (ValueError, TypeError):
                        pass
        
        return outdoor_temp

    def get_humidity(self) -> float | None:
        """Get current room humidity."""
        return self._get_sensor_value(self.coordinator.room_config.humidity_sensor_id)

    def is_window_open(self) -> bool:
        """Check if any window is open."""
        window_ids = self.coordinator.room_config.window_sensor_ids
        if not window_ids:
            return False
            
        for entity_id in window_ids:
            state = self.hass.states.get(entity_id)
            if state and state.state == "on":
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
