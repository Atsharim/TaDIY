"""Sensor platform for TaDIY integration."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_TEMPERATURE, ICON_LEARNING, ICON_MODE
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass
class TaDIYSensorEntityDescription(SensorEntityDescription):
    """Describes TaDIY sensor entity."""
    value_fn: Callable[[Any], Any] | None = None
    available_fn: Callable[[Any], bool] | None = None
    attr_fn: Callable[[Any], dict[str, Any]] | None = None


ROOM_SENSOR_TYPES: tuple[TaDIYSensorEntityDescription, ...] = (
    TaDIYSensorEntityDescription(
        key="current_temperature",
        name="Current Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: data.current_temperature if data else None,
        available_fn=lambda data: data is not None and data.current_temperature is not None,
    ),
    TaDIYSensorEntityDescription(
        key="target_temperature",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: data.target_temperature if data else None,
        available_fn=lambda data: data is not None and data.target_temperature is not None,
    ),
    TaDIYSensorEntityDescription(
        key="heating_rate",
        name="Heating Rate",
        native_unit_of_measurement="°C/h",
        icon=ICON_LEARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: round(data.heating_rate, 2) if data and data.heating_rate else None,
        available_fn=lambda data: data is not None and data.heating_rate is not None,
    ),
)

HUB_SENSOR_TYPES: tuple[TaDIYSensorEntityDescription, ...] = (
    TaDIYSensorEntityDescription(
        key="hub_mode",
        name="Hub Mode",
        icon=ICON_MODE,
        value_fn=lambda data: data.get("hub_mode", "unknown") if data else "unknown",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[SensorEntity] = []

    if entry_type == "hub":
        for description in HUB_SENSOR_TYPES:
            entities.append(TaDIYHubSensor(coordinator, description, entry))
        _LOGGER.info("Added %d hub sensor entities", len(entities))
    elif entry_type == "room":
        for description in ROOM_SENSOR_TYPES:
            entities.append(TaDIYRoomSensor(coordinator, description, entry))
        _LOGGER.info("Added %d room sensor entities", len(entities))

    async_add_entities(entities)


class TaDIYRoomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Room Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if self.entity_description.available_fn is not None:
            return self.entity_description.available_fn(self.coordinator.data)
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYHubSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Hub Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()