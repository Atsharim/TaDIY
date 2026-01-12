"""The TaDIY integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_DURATION_MINUTES,
    ATTR_HEATING_RATE,
    ATTR_MODE,
    ATTR_ROOM,
    ATTR_TEMPERATURE,
    CONF_HUB,
    CONF_ROOM_NAME,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMPERATURE,
    DOMAIN,
    HUB_MODES,
    MAX_BOOST_DURATION,
    MAX_BOOST_TEMP,
    MAX_HEATING_RATE,
    MIN_BOOST_DURATION,
    MIN_BOOST_TEMP,
    MIN_HEATING_RATE,
    SERVICE_BOOST_ALL_ROOMS,
    SERVICE_FORCE_REFRESH,
    SERVICE_RESET_LEARNING,
    SERVICE_SET_HEATING_CURVE,
    SERVICE_SET_HUB_MODE,
)
from .coordinator_hub import TaDIYHubCoordinator
from .coordinator_room import TaDIYRoomCoordinator

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

SERVICE_RESET_LEARNING_SCHEMA = vol.Schema({vol.Optional(ATTR_ROOM): cv.string})
SERVICE_BOOST_ALL_SCHEMA = vol.Schema({
    vol.Optional(ATTR_TEMPERATURE, default=DEFAULT_BOOST_TEMPERATURE): vol.All(
        vol.Coerce(float), vol.Range(min=MIN_BOOST_TEMP, max=MAX_BOOST_TEMP)
    ),
    vol.Optional(ATTR_DURATION_MINUTES, default=DEFAULT_BOOST_DURATION): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_BOOST_DURATION, max=MAX_BOOST_DURATION)
    ),
})
SERVICE_SET_HUB_MODE_SCHEMA = vol.Schema({vol.Required(ATTR_MODE): vol.In(HUB_MODES)})
SERVICE_SET_HEATING_CURVE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ROOM): cv.string,
    vol.Required(ATTR_HEATING_RATE): vol.All(
        vol.Coerce(float), vol.Range(min=MIN_HEATING_RATE, max=MAX_HEATING_RATE)
    ),
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TaDIY component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data.get(CONF_HUB, False):
        return await async_setup_hub(hass, entry)
    else:
        return await async_setup_room(hass, entry)


async def async_setup_hub(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY Hub."""
    _LOGGER.info("Setting up TaDIY Hub: %s", entry.data.get(CONF_NAME))

    hub_coordinator = TaDIYHubCoordinator(hass, entry.entry_id, entry.data)
    await hub_coordinator.async_load_learning_data()
    await hub_coordinator.async_load_schedules()
    await hub_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN]["hub_coordinator"] = hub_coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": hub_coordinator,
        "type": "hub",
        "entry": entry,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await async_register_services(hass, hub_coordinator, entry)
    return True


async def async_setup_room(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY Room."""
    room_name = entry.data.get(CONF_ROOM_NAME, "Unknown")
    _LOGGER.info("Setting up TaDIY Room: %s", room_name)

    hub_coordinator = hass.data[DOMAIN].get("hub_coordinator")
    if not hub_coordinator:
        _LOGGER.error("Hub coordinator not found for room setup")
        return False

    room_coordinator = TaDIYRoomCoordinator(hass, entry.entry_id, entry.data, hub_coordinator)
    await room_coordinator.async_load_schedules()
    await room_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": room_coordinator,
        "type": "room",
        "entry": entry,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_register_services(
    hass: HomeAssistant,
    hub_coordinator: TaDIYHubCoordinator,
    entry: ConfigEntry,
) -> None:
    """Register services for TaDIY."""

    async def handle_force_refresh(call: ServiceCall) -> None:
        await hub_coordinator.async_request_refresh()
        _LOGGER.info("Force refresh triggered")

    async def handle_reset_learning(call: ServiceCall) -> None:
        room_name = call.data.get(ATTR_ROOM)
        if room_name:
            if room_name in hub_coordinator.heat_models:
                from .core.early_start import HeatUpModel
                hub_coordinator.heat_models[room_name] = HeatUpModel(room_name=room_name)
                await hub_coordinator.async_save_learning_data()
                _LOGGER.info("Learning data reset for room: %s", room_name)
        else:
            from .core.early_start import HeatUpModel
            for room_name in hub_coordinator.heat_models:
                hub_coordinator.heat_models[room_name] = HeatUpModel(room_name=room_name)
            await hub_coordinator.async_save_learning_data()
            _LOGGER.info("Learning data reset for all rooms")

    async def handle_boost_all_rooms(call: ServiceCall) -> None:
        temperature = call.data.get(ATTR_TEMPERATURE, DEFAULT_BOOST_TEMPERATURE)
        duration = call.data.get(ATTR_DURATION_MINUTES, DEFAULT_BOOST_DURATION)
        
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("type") == "room":
                room_coord = data["coordinator"]
                for trv_entity_id in room_coord.room_config.trv_entity_ids:
                    try:
                        await hass.services.async_call(
                            "climate",
                            "set_temperature",
                            {"entity_id": trv_entity_id, "temperature": temperature},
                            blocking=True,
                        )
                    except Exception as err:
                        _LOGGER.error("Failed to boost TRV %s: %s", trv_entity_id, err)

    async def handle_set_hub_mode(call: ServiceCall) -> None:
        mode = call.data.get(ATTR_MODE)
        if mode not in HUB_MODES:
            _LOGGER.error("Invalid mode: %s", mode)
            return

        hub_coordinator.hub_mode = mode
        await hub_coordinator.async_request_refresh()

        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("type") == "room":
                await data["coordinator"].async_request_refresh()

    async def handle_set_heating_curve(call: ServiceCall) -> None:
        room_name = call.data.get(ATTR_ROOM)
        heating_rate = call.data.get(ATTR_HEATING_RATE)

        if room_name in hub_coordinator.heat_models:
            hub_coordinator.heat_models[room_name].heating_rate = heating_rate
            await hub_coordinator.async_save_learning_data()
            _LOGGER.info("Heating rate for room %s set to %.2f °C/h", room_name, heating_rate)
        else:
            _LOGGER.error("Room not found: %s", room_name)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_REFRESH, handle_force_refresh)
    hass.services.async_register(DOMAIN, SERVICE_RESET_LEARNING, handle_reset_learning, schema=SERVICE_RESET_LEARNING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BOOST_ALL_ROOMS, handle_boost_all_rooms, schema=SERVICE_BOOST_ALL_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_HUB_MODE, handle_set_hub_mode, schema=SERVICE_SET_HUB_MODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_HEATING_CURVE, handle_set_heating_curve, schema=SERVICE_SET_HEATING_CURVE_SCHEMA)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if not entry_data:
        return True

    coordinator = entry_data["coordinator"]

    if entry_data.get("type") == "hub":
        await coordinator.async_save_learning_data()
        await coordinator.async_save_schedules()
    elif entry_data.get("type") == "room":
        await coordinator.async_save_schedules()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if entry_data.get("type") == "hub":
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_REFRESH)
            hass.services.async_remove(DOMAIN, SERVICE_RESET_LEARNING)
            hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL_ROOMS)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HUB_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HEATING_CURVE)
            hass.data[DOMAIN].pop("hub_coordinator", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)