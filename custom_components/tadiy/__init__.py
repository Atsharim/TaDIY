"""The TaDIY integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import (
    ATTR_DURATION_MINUTES,
    ATTR_MODE,
    ATTR_ROOM,
    ATTR_TEMPERATURE,
    CONF_ROOMS,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMPERATURE,
    DEFAULT_FROST_PROTECTION_TEMP,
    DEFAULT_HUB_MODE,
    DOMAIN,
    HUB_MODES,
    MANUFACTURER,
    MAX_BOOST_DURATION,
    MAX_BOOST_TEMP,
    MIN_BOOST_DURATION,
    MIN_BOOST_TEMP,
    MODEL_NAME,
    SERVICE_BOOST_ALL_ROOMS,
    SERVICE_FORCE_REFRESH,
    SERVICE_RESET_LEARNING,
    SERVICE_SET_HUB_MODE,
)
from .coordinator import TaDIYDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service schemas
SERVICE_RESET_LEARNING_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ROOM): cv.string,
    }
)

SERVICE_BOOST_ALL_SCHEMA = vol.Schema(
    {
        vol.Optional(
            ATTR_TEMPERATURE, default=DEFAULT_BOOST_TEMPERATURE
        ): vol.All(vol.Coerce(float), vol.Range(min=MIN_BOOST_TEMP, max=MAX_BOOST_TEMP)),
        vol.Optional(
            ATTR_DURATION_MINUTES, default=DEFAULT_BOOST_DURATION
        ): vol.All(vol.Coerce(int), vol.Range(min=MIN_BOOST_DURATION, max=MAX_BOOST_DURATION)),
    }
)

SERVICE_SET_HUB_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MODE): vol.In(HUB_MODES),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TaDIY component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    rooms = entry.options.get(CONF_ROOMS, [])
    
    # Initialize coordinator with schedule support
    coordinator = TaDIYDataUpdateCoordinator(
        hass, 
        entry.entry_id, 
        entry.data, 
        rooms,
        hub_mode=DEFAULT_HUB_MODE,
        frost_protection_temp=DEFAULT_FROST_PROTECTION_TEMP,
    )

    await coordinator.async_load_learning_data()
    await coordinator.async_load_schedules()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Create Hub device
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

    # Register services
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

    async def handle_boost_all_rooms(call: ServiceCall) -> None:
        """Handle boost all rooms service."""
        temperature = call.data.get(ATTR_TEMPERATURE, DEFAULT_BOOST_TEMPERATURE)
        duration = call.data.get(ATTR_DURATION_MINUTES, DEFAULT_BOOST_DURATION)

        _LOGGER.info(
            "Boost all rooms triggered: %.1f°C for %d minutes",
            temperature,
            duration,
        )

        for room in coordinator.rooms:
            for trv_entity_id in room.trv_entity_ids:
                try:
                    await hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            "entity_id": trv_entity_id,
                            "temperature": temperature,
                        },
                        blocking=True,
                    )
                    _LOGGER.debug("Boost set for TRV: %s", trv_entity_id)
                except Exception as err:
                    _LOGGER.error("Failed to boost TRV %s: %s", trv_entity_id, err)

        await coordinator.async_request_refresh()

    async def handle_set_hub_mode(call: ServiceCall) -> None:
        """Handle set hub mode service."""
        mode = call.data.get(ATTR_MODE)

        if mode not in HUB_MODES:
            _LOGGER.error("Invalid mode: %s", mode)
            return

        # Update select entity
        select_entity_id = "select.tadiy_hub_mode"
        try:
            await hass.services.async_call(
                "select",
                "select_option",
                {
                    "entity_id": select_entity_id,
                    "option": mode,
                },
                blocking=True,
            )
            _LOGGER.info("Hub mode changed to: %s", mode)
        except Exception as err:
            _LOGGER.error("Failed to set hub mode: %s", err)

    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_REFRESH, handle_force_refresh
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_LEARNING,
        handle_reset_learning,
        schema=SERVICE_RESET_LEARNING_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_BOOST_ALL_ROOMS,
        handle_boost_all_rooms,
        schema=SERVICE_BOOST_ALL_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HUB_MODE,
        handle_set_hub_mode,
        schema=SERVICE_SET_HUB_MODE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_save_learning_data()
    await coordinator.async_save_schedules()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_REFRESH)
            hass.services.async_remove(DOMAIN, SERVICE_RESET_LEARNING)
            hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL_ROOMS)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HUB_MODE)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
