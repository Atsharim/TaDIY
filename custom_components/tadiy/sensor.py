"""Sensor platform for TaDIY."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_CATEGORY_DIAGNOSTIC
from .coordinator import TaDIYDataUpdateCoordinator
from .models.room import RoomData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    coordinator: TaDIYDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for room in coordinator.rooms:
        # Temperature sensors
        entities.append(TaDIYMainTemperatureSensor(coordinator, room.name))
        entities.append(TaDIYFusedTemperatureSensor(coordinator, room.name))
        
        # Window status sensor
        entities.append(TaDIYWindowStateSensor(coordinator, room.name))
        
        # Heating rate sensor (for early-start learning)
        entities.append(TaDIYHeatingRateSensor(coordinator, room.name))

    async_add_entities(entities)
    _LOGGER.info("TaDIY sensor platform setup complete (%d sensors)", len(entities))


class TaDIYBaseSensor(CoordinatorEntity[TaDIYDataUpdateCoordinator], SensorEntity):
    """Base class for TaDIY sensors."""

    def __init__(
        self, 
        coordinator: TaDIYDataUpdateCoordinator, 
        room_name: str,
        sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{room_name.lower().replace(' ', '_')}_{sensor_type}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{room_name.lower().replace(' ', '_')}")},
            "name": f"TaDIY {room_name}",
        }

    @property
    def room_data(self) -> RoomData | None:
        """Get current room data from coordinator."""
        return self.coordinator.data.get(self._room_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.room_data is not None


class TaDIYMainTemperatureSensor(TaDIYBaseSensor):
    """Sensor for main room temperature (from primary sensor)."""

    def __init__(self, coordinator: TaDIYDataUpdateCoordinator, room_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, room_name, "main_temperature")
        self._attr_name = "Main Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if room_data := self.room_data:
            return room_data.main_sensor_temperature
        return None


class TaDIYFusedTemperatureSensor(TaDIYBaseSensor):
    """Sensor for fused temperature (weighted average)."""

    def __init__(self, coordinator: TaDIYDataUpdateCoordinator, room_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, room_name, "fused_temperature")
        self._attr_name = "Fused Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if room_data := self.room_data:
            return room_data.current_temperature
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if room_data := self.room_data:
            return {
                "trv_temperatures": room_data.trv_temperatures,
                "sensor_count": len(room_data.trv_temperatures) + 1,
            }
        return {}


class TaDIYWindowStateSensor(TaDIYBaseSensor):
    """Sensor for window state."""

    def __init__(self, coordinator: TaDIYDataUpdateCoordinator, room_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, room_name, "window_state")
        self._attr_name = "Window State"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["closed", "open", "no_sensors"]
        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if room_data := self.room_data:
            if room_data.window_state.reason == "no_sensors":
                return "no_sensors"
            return "open" if room_data.window_state.is_open else "closed"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if room_data := self.room_data:
            attrs = {
                "reason": room_data.window_state.reason,
            }
            if room_data.window_state.last_change:
                attrs["last_change"] = room_data.window_state.last_change.isoformat()
            return attrs
        return {}


class TaDIYHeatingRateSensor(TaDIYBaseSensor):
    """Sensor for learned heating rate (°C per hour)."""

    def __init__(self, coordinator: TaDIYDataUpdateCoordinator, room_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, room_name, "heating_rate")
        self._attr_name = "Heating Rate"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "°C/h"
        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
        self._attr_icon = "mdi:thermometer-chevron-up"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if room_data := self.room_data:
            return round(room_data.heating_rate, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "info": "Learned heating rate for early-start calculation",
        }
