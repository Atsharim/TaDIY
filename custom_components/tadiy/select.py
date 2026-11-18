"""Select platform for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BOILER_MIN_RUN_TIME,
    CONF_BOILER_TEMP_SENSOR,
    CONF_BOOST_DURATION,
    CONF_BOOST_TEMPERATURE,
    CONF_CYCLE_LOCK_ON_SETPOINT_DROP,
    CONF_DHW_TEMP_SENSOR,
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_FROST_PROTECTION_TEMP,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_OFFSET_DURATION_HOURS,
    CONF_GLOBAL_OFFSET_MODE,
    CONF_GLOBAL_OFFSET_STEP,
    CONF_GLOBAL_OVERRIDE_TIMEOUT,
    CONF_PERSON_ENTITIES,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_HOUSE_SETBACK_DELTA,
    CONF_WINDOW_NEIGHBOR_SETBACK_DELTA,
    CONF_WINDOW_NEIGHBOR_SETBACK_ENABLED,
    CONF_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    ICON_MODE,
)

_LOGGER = logging.getLogger(__name__)


HUB_SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="hub_mode",
        name="Mode",
        icon=ICON_MODE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY select entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[SelectEntity] = []

    if entry_type == "hub":
        # Hub selects
        for description in HUB_SELECT_TYPES:
            entities.append(
                TaDIYHubSelect(
                    coordinator=coordinator,
                    description=description,
                    entry_id=entry.entry_id,
                )
            )
        _LOGGER.info("Added %d hub select entities", len(entities))

    elif entry_type == "room":
        # Room doesn't have select entities currently
        _LOGGER.debug("Room entry - no select entities")
        return

    async_add_entities(entities)


class TaDIYHubSelect(CoordinatorEntity, SelectEntity):
    """Representation of a TaDIY Hub Select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_name = description.name

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
        }

    @property
    def options(self) -> list[str]:
        """Return available options dynamically from coordinator."""
        if self.entity_description.key == "hub_mode":
            return self.coordinator.get_custom_modes()
        return []

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        if self.entity_description.key == "hub_mode":
            return self.coordinator.get_hub_mode()
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return hub configuration options and boiler attributes."""
        if self.entity_description.key == "hub_mode":
            cfg = getattr(self.coordinator, "config_data", {})
            return {
                CONF_FROST_PROTECTION_TEMP: getattr(
                    self.coordinator, "frost_protection_temp", 7.0
                ),
                CONF_BOOST_TEMPERATURE: cfg.get(CONF_BOOST_TEMPERATURE, 24.0),
                CONF_BOOST_DURATION: cfg.get(CONF_BOOST_DURATION, 60),
                CONF_WINDOW_OPEN_TIMEOUT: cfg.get(CONF_WINDOW_OPEN_TIMEOUT, 30),
                CONF_WINDOW_CLOSE_TIMEOUT: cfg.get(CONF_WINDOW_CLOSE_TIMEOUT, 60),
                CONF_GLOBAL_OVERRIDE_TIMEOUT: cfg.get(
                    CONF_GLOBAL_OVERRIDE_TIMEOUT, 120
                ),
                CONF_DONT_HEAT_BELOW_OUTDOOR: cfg.get(
                    CONF_DONT_HEAT_BELOW_OUTDOOR, cfg.get(CONF_GLOBAL_DONT_HEAT_BELOW)
                ),
                CONF_BOILER_MIN_RUN_TIME: cfg.get(CONF_BOILER_MIN_RUN_TIME, 300),
                CONF_CYCLE_LOCK_ON_SETPOINT_DROP: cfg.get(
                    CONF_CYCLE_LOCK_ON_SETPOINT_DROP, True
                ),
                CONF_BOILER_TEMP_SENSOR: getattr(
                    self.coordinator, "boiler_temp_sensor", None
                ),
                "boiler_temperature": getattr(
                    self.coordinator, "boiler_temperature", None
                ),
                "boiler_sensor_available": getattr(
                    self.coordinator, "boiler_sensor_available", True
                ),
                "boiler_active": getattr(self.coordinator, "boiler_active", False),
                CONF_DHW_TEMP_SENSOR: getattr(
                    self.coordinator, "dhw_temp_sensor", cfg.get(CONF_DHW_TEMP_SENSOR)
                ),
                "dhw_temperature": getattr(self.coordinator, "dhw_temperature", None),
                "dhw_sensor_available": getattr(
                    self.coordinator, "dhw_sensor_available", True
                ),
                "homeoffice_tomorrow": getattr(
                    self.coordinator, "_homeoffice_tomorrow", False
                ),
                CONF_PERSON_ENTITIES: getattr(
                    self.coordinator,
                    "person_entities",
                    cfg.get(CONF_PERSON_ENTITIES, []),
                ),
                CONF_WINDOW_NEIGHBOR_SETBACK_ENABLED: getattr(
                    self.coordinator, "window_neighbor_setback_enabled", True
                ),
                CONF_WINDOW_NEIGHBOR_SETBACK_DELTA: getattr(
                    self.coordinator, "window_neighbor_setback_delta", 1.5
                ),
                CONF_WINDOW_HOUSE_SETBACK_DELTA: getattr(
                    self.coordinator, "window_house_setback_delta", 1.0
                ),
                CONF_GLOBAL_OFFSET_STEP: getattr(
                    self.coordinator, "global_offset_step", 1.5
                ),
                CONF_GLOBAL_OFFSET_MODE: getattr(
                    self.coordinator, "global_offset_mode", "next_block"
                ),
                CONF_GLOBAL_OFFSET_DURATION_HOURS: getattr(
                    self.coordinator, "global_offset_duration_hours", 3.0
                ),
                "global_offset_temp": getattr(
                    self.coordinator, "global_offset_temp", 0.0
                ),
                "global_offset_until": (
                    getattr(self.coordinator, "global_offset_until", None).isoformat()
                    if getattr(self.coordinator, "global_offset_until", None)
                    else None
                ),
            }
        return {}

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self.entity_description.key == "hub_mode":
            available_modes = self.coordinator.get_custom_modes()
            if option in available_modes:
                self.coordinator.set_hub_mode(option)
                await self.coordinator.async_save_schedules()
                await self.coordinator.async_request_refresh()
                _LOGGER.info("Hub mode changed to: %s", option)
            else:
                _LOGGER.error(
                    "Invalid hub mode: %s (available: %s)", option, available_modes
                )

        self.async_write_ha_state()
