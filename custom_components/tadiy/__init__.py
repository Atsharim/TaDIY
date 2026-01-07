"""The TaDIY integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_ROOM,
    CONF_ROOMS,
    DOMAIN,
    MANUFACTURER,
    MODEL_NAME,
    SERVICE_FORCE_REFRESH,
    SERVICE_RESET_LEARNING,
)
from .coordinator import TaDIYDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TaDIY component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    rooms = entry.options.get(CONF_ROOMS, [])
    coordinator = TaDIYDataUpdateCoordinator(
        hass, entry.entry_id, entry.data, rooms
    )

    await coordinator.async_load_learning_data()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, "TaDIY Hub"),
        manufacturer=MANUFACTURER,
        model=MODEL_NAME,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    async def handle_force_refresh(call: ServiceCall) -> None:
        """Handle force refresh service."""
        await coordinator.async_request_refresh()
        _LOGGER.info("Force refresh triggered for %s", entry.data.get(CONF_NAME))

    async def handle_reset_learning(call: ServiceCall) -> None:
        """Handle reset learning service."""
        room_name = call.data.get(ATTR_ROOM)

        if room_name:
            if room_name in coordinator._heat_models:
                from .core.early_start import HeatUpModel

                coordinator._heat_models[room_name] = HeatUpModel(room_name=room_name)
                await coordinator.async_save_learning_data()
                _LOGGER.info("Learning data reset for room: %s", room_name)
            else:
                _LOGGER.warning("Room %s not found", room_name)
        else:
            from .core.early_start import HeatUpModel

            for room_name in coordinator._heat_models:
                coordinator._heat_models[room_name] = HeatUpModel(room_name=room_name)
            await coordinator.async_save_learning_data()
            _LOGGER.info("Learning data reset for all rooms")

    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_REFRESH, handle_force_refresh
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESET_LEARNING, handle_reset_learning
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_save_learning_data()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_REFRESH)
            hass.services.async_remove(DOMAIN, SERVICE_RESET_LEARNING)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
