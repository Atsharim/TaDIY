"""Number platform for TaDIY."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_FROST_PROTECTION_TEMP,
    DEFAULT_FROST_PROTECTION_TEMP,
    DOMAIN,
    ICON_FROST,
    MANUFACTURER,
    MAX_FROST_PROTECTION,
    MIN_FROST_PROTECTION,
    MODEL_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY number entities."""
    entities = [
        TaDIYFrostProtectionNumber(
            config_entry.entry_id,
            config_entry.data.get(
                CONF_FROST_PROTECTION_TEMP, DEFAULT_FROST_PROTECTION_TEMP
            ),
        )
    ]
    
    async_add_entities(entities)
    _LOGGER.info("TaDIY number platform setup complete")


class TaDIYFrostProtectionNumber(NumberEntity, RestoreEntity):
    """Number entity for frost protection temperature."""

    _attr_icon = ICON_FROST
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_FROST_PROTECTION
    _attr_native_max_value = MAX_FROST_PROTECTION
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, entry_id: str, initial_temp: float) -> None:
        """Initialize the number entity."""
        self._entry_id = entry_id
        self._attr_name = "TaDIY Frost Protection"
        self._attr_unique_id = f"{entry_id}_frost_protection"
        self._attr_native_value = initial_temp
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "TaDIY Hub",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Update the frost protection temperature."""
        self._attr_native_value = value
        self.async_write_ha_state()
        
        _LOGGER.info("Frost protection temperature set to: %.1f°C", value)
        
        # Update schedule engine
        coordinator = self.hass.data[DOMAIN][self._entry_id]["coordinator"]
        if hasattr(coordinator, "schedule_engine"):
            coordinator.schedule_engine.set_frost_protection_temp(value)
        
        # Trigger update to apply new temp
        await coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last value when added to hass."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
                _LOGGER.debug(
                    "Restored frost protection temp: %.1f°C",
                    self._attr_native_value,
                )
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore frost protection temp")

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._attr_native_value
