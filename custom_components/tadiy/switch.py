"""Switch platform for TaDIY."""

from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_HUB,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_USE_EARLY_START,
    DOMAIN,
    MANUFACTURER,
    MODEL_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY switch entities."""
    if not config_entry.data.get(CONF_HUB):
        return
    entities = [
        TaDIYUseEarlyStartSwitch(
            config_entry.entry_id,
            DEFAULT_USE_EARLY_START,
        ),
        TaDIYLearnHeatingRateSwitch(
            config_entry.entry_id,
            DEFAULT_LEARN_HEATING_RATE,
        ),
    ]
    async_add_entities(entities)
    _LOGGER.info("TaDIY switch platform setup complete")


class TaDIYUseEarlyStartSwitch(SwitchEntity, RestoreEntity):
    """Switch entity for use early start (global)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry_id: str, initial_state: bool) -> None:
        """Initialize the switch entity."""
        self._entry_id = entry_id
        self._attr_name = "TaDIY Global Use Early Start"
        self._attr_unique_id = entry_id + "_use_early_start"
        self._attr_is_on = initial_state
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "TaDIY Hub",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on early start."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.info("Global use early start enabled")
        coordinator = self.hass.data[DOMAIN].get("hub_coordinator")
        if coordinator:
            coordinator.global_settings[CONF_GLOBAL_USE_EARLY_START] = True
            await coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off early start."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.info("Global use early start disabled")
        coordinator = self.hass.data[DOMAIN].get("hub_coordinator")
        if coordinator:
            coordinator.global_settings[CONF_GLOBAL_USE_EARLY_START] = False
            await coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last value when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug("Restored use early start: %s", last_state.state)


class TaDIYLearnHeatingRateSwitch(SwitchEntity, RestoreEntity):
    """Switch entity for learn heating rate (global)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry_id: str, initial_state: bool) -> None:
        """Initialize the switch entity."""
        self._entry_id = entry_id
        self._attr_name = "TaDIY Global Learn Heating Rate"
        self._attr_unique_id = entry_id + "_learn_heating_rate"
        self._attr_is_on = initial_state
        self._attr_icon = "mdi:school"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "TaDIY Hub",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on learning."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.info("Global learn heating rate enabled")
        coordinator = self.hass.data[DOMAIN].get("hub_coordinator")
        if coordinator:
            coordinator.global_settings[CONF_GLOBAL_LEARN_HEATING_RATE] = True
            await coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off learning."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.info("Global learn heating rate disabled")
        coordinator = self.hass.data[DOMAIN].get("hub_coordinator")
        if coordinator:
            coordinator.global_settings[CONF_GLOBAL_LEARN_HEATING_RATE] = False
            await coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last value when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug("Restored learn heating rate: %s", last_state.state)
