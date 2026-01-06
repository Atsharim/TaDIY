"""Climate platform for TaDIY."""
from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaDIYCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY climate entities."""
    coordinator: TaDIYCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Später: Räume dynamisch aus Config laden
    entities: list[TaDIYClimate] = [
        TaDIYClimate(coordinator, "test_room"),
    ]

    async_add_entities(entities)
    _LOGGER.info("TaDIY climate platform setup complete (%d entities)", len(entities))


class TaDIYClimate(CoordinatorEntity[TaDIYCoordinator], ClimateEntity):
    """TaDIY Climate Entity (TRV Wrapper)."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(self, coordinator: TaDIYCoordinator, room_name: str) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_unique_id = f"tadiy_{room_name}"
        self._attr_name = f"TaDIY {room_name.replace('_', ' ').title()}"

        # Dummy-Werte für ersten Test
        self._attr_current_temperature = 20.0
        self._attr_target_temperature = 21.0
        self._attr_hvac_mode = HVACMode.HEAT

        _LOGGER.debug("TaDIY Climate created: %s", self._attr_name)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        self._attr_target_temperature = float(temperature)
        self.async_write_ha_state()
        _LOGGER.info(
            "%s: Target temperature set to %.1f°C",
            self._attr_name,
            self._attr_target_temperature,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        _LOGGER.info("%s: HVAC mode set to %s", self._attr_name, hvac_mode)
