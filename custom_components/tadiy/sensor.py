"""Sensor platform for TaDIY."""

from __future__ import annotations

import logging

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

from .const import (
    ATTR_LEARNING_SAMPLES,
    ATTR_LAST_LEARNING_UPDATE,
    DOMAIN,
    ICON_HEATING,
    ICON_TEMPERATURE,
    ICON_WINDOW,
    MANUFACTURER,
    MODEL_NAME,
    SENSOR_TYPE_HEATING_RATE,
    SENSOR_TYPE_MAIN_TEMP,
    SENSOR_TYPE_OUTDOOR_TEMP,
    SENSOR_TYPE_WINDOW_STATE,
    WINDOW_STATE_CLOSED,
    WINDOW_STATE_CLOSED_COOLDOWN,
    WINDOW_STATE_OPEN_HEATING_STOPPED,
    WINDOW_STATE_OPEN_WITHIN_TIMEOUT,
)
from .coordinator import TaDIYDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: TaDIYDataUpdateCoordinator = data["coordinator"]

    sensors: list[SensorEntity] = []

    for room_name in coordinator.data.keys():
        sensors.extend([
            TaDIYTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
                SENSOR_TYPE_MAIN_TEMP,
                "Main Temperature",
            ),
            TaDIYTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
                SENSOR_TYPE_OUTDOOR_TEMP,
                "Outdoor Temperature",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            TaDIYTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
                "fused",
                "Fused Temperature",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            TaDIYWindowStateSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            ),
            TaDIYHeatingRateSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            ),
        ])

    async_add_entities(sensors)


class TaDIYTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Temperature sensor for TaDIY rooms."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = ICON_TEMPERATURE

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
        sensor_type: str,
        name: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._sensor_type = sensor_type
        self._attr_name = f"{room_name} {name}"
        self._attr_unique_id = f"{entry_id}_{room_name}_{sensor_type}_temp"
        self._attr_entity_category = entity_category
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return None

        if self._sensor_type == SENSOR_TYPE_MAIN_TEMP:
            return room_data.main_sensor_temperature
        elif self._sensor_type == SENSOR_TYPE_OUTDOOR_TEMP:
            return room_data.outdoor_temperature
        elif self._sensor_type == "fused":
            return room_data.current_temperature

        return None


class TaDIYWindowStateSensor(CoordinatorEntity, SensorEntity):
    """Window state sensor for TaDIY rooms."""

    _attr_icon = ICON_WINDOW

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Window State"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_WINDOW_STATE}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return None

        if room_data.window_state.is_open:
            if room_data.window_state.timeout_active:
                return WINDOW_STATE_OPEN_HEATING_STOPPED
            return WINDOW_STATE_OPEN_WITHIN_TIMEOUT
        else:
            if room_data.window_state.timeout_active:
                return WINDOW_STATE_CLOSED_COOLDOWN
            return WINDOW_STATE_CLOSED

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return {}

        return {
            "is_open": room_data.window_state.is_open,
            "heating_should_stop": room_data.window_state.heating_should_stop,
            "reason": room_data.window_state.reason,
            "last_change": (
                room_data.window_state.last_change.isoformat()
                if room_data.window_state.last_change
                else None
            ),
        }


class TaDIYHeatingRateSensor(CoordinatorEntity, SensorEntity):
    """Heating rate sensor for learning data."""

    _attr_icon = ICON_HEATING
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Heating Rate"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_HEATING_RATE}"
        self._attr_native_unit_of_measurement = "°C/h"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the learned heating rate."""
        heat_model = self.coordinator._heat_models.get(self._room_name)
        if heat_model:
            return round(heat_model.degrees_per_hour, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return learning statistics."""
        heat_model = self.coordinator._heat_models.get(self._room_name)
        if not heat_model:
            return {}

        return {
            ATTR_LEARNING_SAMPLES: heat_model.sample_count,
            ATTR_LAST_LEARNING_UPDATE: (
                heat_model.last_updated.isoformat()
                if heat_model.last_updated
                else None
            ),
        }
