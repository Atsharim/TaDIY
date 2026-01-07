"""Select platform for TaDIY."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_HUB_MODE,
    DEFAULT_HUB_MODE,
    DOMAIN,
    HUB_MODES,
    ICON_MODE,
    MANUFACTURER,
    MODEL_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY select entities."""
    entities = [
        TaDIYHubModeSelect(
            config_entry.entry_id,
            config_entry.data.get(CONF_HUB_MODE, DEFAULT_HUB_MODE),
        )
    ]
    
    async_add_entities(entities)
    _LOGGER.info("TaDIY select platform setup complete")


class TaDIYHubModeSelect(SelectEntity, RestoreEntity):
    """Select entity for TaDIY Hub mode."""

    _attr_icon = ICON_MODE
    _attr_options = HUB_MODES

    def __init__(self, entry_id: str, initial_mode: str) -> None:
        """Initialize the select entity."""
        self._entry_id = entry_id
        self._attr_name = "TaDIY Hub Mode"
        self._attr_unique_id = f"{entry_id}_hub_mode"
        self._attr_current_option = initial_mode
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "TaDIY Hub",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in HUB_MODES:
            _LOGGER.error("Invalid mode selected: %s", option)
            return

        self._attr_current_option = option
        self.async_write_ha_state()
        
        _LOGGER.info("Hub mode changed to: %s", option)
        
        # Trigger coordinator update to apply new mode
        coordinator = self.hass.data[DOMAIN][self._entry_id]["coordinator"]
        await coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last state when added to hass."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in HUB_MODES:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored hub mode: %s", last_state.state)

    @property
    def current_option(self) -> str:
        """Return the selected option."""
        return self._attr_current_option
