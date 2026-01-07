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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaDIYCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    coordinator: TaDIYCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors: list[SensorEntity] = []
    
    for room_id, room_data in coordinator.data.get("rooms", {}).items():
        sensors.extend([
            TaDIYTemperatureSensor(
                coordinator,
                config_entry,
                room_id,
                "main_temp",
                "Main Temperature",
            ),
            TaDIYTemperatureSensor(
                coordinator,
                config_entry,
                room_id,
                "outdoor_temp",
                "Outdoor Temperature",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            TaDIYWindowStateSensor(coordinator, config_entry, room_id),
        ])

    async_add_entities(sensors)


class TaDIYTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Temperature sensor for TaDIY rooms."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: TaDIYCoordinator,
        config_entry: ConfigEntry,
        room_id: str,
        sensor_type: str,
        name: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_id = room_id
        self._sensor_type = sensor_type
        self._attr_name = f"{room_id} {name}"
        self._attr_unique_id = f"{config_entry.entry_id}_{room_id}_{sensor_type}"
        self._attr_entity_category = entity_category
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{config_entry.entry_id}_{room_id}")},
            "name": f"TaDIY {room_id}",
            "manufacturer": "TaDIY",
            "model": "Climate Orchestrator",
            "sw_version": "1.0.0",
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        room_data = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
        return room_data.get(self._sensor_type)


class TaDIYWindowStateSensor(CoordinatorEntity, SensorEntity):
    """Window state sensor for TaDIY rooms."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(
        self,
        coordinator: TaDIYCoordinator,
        config_entry: ConfigEntry,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{room_id} Window State"
        self._attr_unique_id = f"{config_entry.entry_id}_{room_id}_window_state"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{config_entry.entry_id}_{room_id}")},
            "name": f"TaDIY {room_id}",
            "manufacturer": "TaDIY",
            "model": "Climate Orchestrator",
            "sw_version": "1.0.0",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        room_data = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
        return room_data.get("window_state", "closed")
