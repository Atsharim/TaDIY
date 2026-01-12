"""Number platform for TaDIY integration."""
from __future__ import annotations
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MIN_FROST_PROTECTION,
    MAX_FROST_PROTECTION,
    MIN_BOOST_TEMP,
    MAX_BOOST_TEMP,
    MIN_BOOST_DURATION,
    MAX_BOOST_DURATION,
    ICON_FROST,
    ICON_BOOST,
)
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)

HUB_NUMBER_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="frost_protection_temp",
        name="Frost Protection Temperature",
        native_min_value=MIN_FROST_PROTECTION,
        native_max_value=MAX_FROST_PROTECTION,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=ICON_FROST,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="boost_temperature",
        name="Boost Temperature",
        native_min_value=MIN_BOOST_TEMP,
        native_max_value=MAX_BOOST_TEMP,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=ICON_BOOST,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="boost_duration",
        name="Boost Duration",
        native_min_value=MIN_BOOST_DURATION,
        native_max_value=MAX_BOOST_DURATION,
        native_step=5,
        native_unit_of_measurement="min",
        icon="mdi:timer",
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY number entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[NumberEntity] = []

    if entry_type == "hub":
        for description in HUB_NUMBER_TYPES:
            entities.append(TaDIYHubNumber(coordinator, description, entry))
        _LOGGER.info("Added %d hub number entities", len(entities))
    elif entry_type == "room":
        _LOGGER.debug("Room entry - no number entities")
        return

    async_add_entities(entities)


class TaDIYHubNumber(CoordinatorEntity, NumberEntity):
    """Representation of a TaDIY Hub Number."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description: NumberEntityDescription, entry: ConfigEntry) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.entity_description.key == "frost_protection_temp":
            return self.coordinator.frost_protection_temp
        elif self.entity_description.key == "boost_temperature":
            return self.coordinator.config_data.get("boost_temperature", 30.0)
        elif self.entity_description.key == "boost_duration":
            return self.coordinator.config_data.get("boost_duration_minutes", 60)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.entity_description.key == "frost_protection_temp":
            self.coordinator.set_frost_protection_temp(value)
            await self.coordinator.async_save_schedules()
        elif self.entity_description.key == "boost_temperature":
            self.coordinator.config_data["boost_temperature"] = value
        elif self.entity_description.key == "boost_duration":
            self.coordinator.config_data["boost_duration_minutes"] = int(value)
        
        self.async_write_ha_state()