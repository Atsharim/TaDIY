"""TaDIY - Adaptive Climate Orchestrator integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .coordinator import TaDIYDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY from a config entry."""
    _LOGGER.info("Setting up TaDIY integration (entry_id: %s)", entry.entry_id)

    # Storage for persistent room data
    store = Store[dict[str, Any]](
        hass,
        STORAGE_VERSION,
        f"{STORAGE_KEY}.{entry.entry_id}",
    )

    # Create coordinator
    coordinator = TaDIYDataUpdateCoordinator(hass, entry, store)
    
    # Initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
    }

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Entry update listener (for OptionsFlow)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services
    await async_setup_services(hass)

    _LOGGER.info("TaDIY integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading TaDIY integration (entry_id: %s)", entry.entry_id)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up data
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.info("Reloading TaDIY integration after options update")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for TaDIY."""
    
    async def handle_force_refresh(call: ServiceCall) -> None:
        """Handle force refresh service."""
        entry_id = call.data.get("entry_id")
        if entry_id and DOMAIN in hass.data and entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            await coordinator.async_refresh()
            _LOGGER.info("Force refresh triggered for entry %s", entry_id)

    # Service: force_refresh (for debugging)
    hass.services.async_register(
        DOMAIN,
        "force_refresh",
        handle_force_refresh,
        schema=vol.Schema({
            vol.Optional("entry_id"): cv.string,
        }),
    )
