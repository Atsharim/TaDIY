"""The TaDIY integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_BLOCKS,
    ATTR_DURATION_MINUTES,
    ATTR_ENTITY_ID,
    ATTR_HEATING_RATE,
    ATTR_MODE,
    ATTR_ROOM,
    ATTR_SCHEDULE_TYPE,
    ATTR_TEMPERATURE,
    CONF_HUB,
    CONF_ROOM_NAME,
    CONF_SHOW_PANEL,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMPERATURE,
    DOMAIN,
    MAX_BOOST_DURATION,
    MAX_BOOST_TEMP,
    MAX_HEATING_RATE,
    MIN_BOOST_DURATION,
    MIN_BOOST_TEMP,
    MIN_HEATING_RATE,
    SERVICE_BOOST_ALL_ROOMS,
    SERVICE_FORCE_REFRESH,
    SERVICE_GET_SCHEDULE,
    SERVICE_RESET_LEARNING,
    SERVICE_SET_HEATING_CURVE,
    SERVICE_SET_HUB_MODE,
    SERVICE_SET_SCHEDULE,
)
from .coordinator import TaDIYHubCoordinator, TaDIYRoomCoordinator

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
SERVICE_SET_HUB_MODE_SCHEMA = vol.Schema({vol.Required(ATTR_MODE): cv.string})
SERVICE_SET_HEATING_CURVE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ROOM): cv.string,
    vol.Required(ATTR_HEATING_RATE): vol.All(
        vol.Coerce(float), vol.Range(min=MIN_HEATING_RATE, max=MAX_HEATING_RATE)
    ),
})
SERVICE_GET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_MODE): cv.string,
    vol.Optional(ATTR_SCHEDULE_TYPE): cv.string,
})
SERVICE_SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_MODE): cv.string,
    vol.Optional(ATTR_SCHEDULE_TYPE): cv.string,
    vol.Required(ATTR_BLOCKS): vol.All(cv.ensure_list, [dict]),
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TaDIY component."""
    hass.data.setdefault(DOMAIN, {})

    # Register static path for Lovelace card
    files_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/tadiy", str(files_path), False),
    ])
    _LOGGER.info("TaDIY: Registered static path /tadiy for Lovelace card")

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

    # Register custom panel in sidebar if enabled
    show_panel = entry.data.get(CONF_SHOW_PANEL, True)
    if show_panel:
        from homeassistant.components import frontend
        await frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            frontend_url_path="tadiy-schedules",
            sidebar_title="TaDIY Schedules",
            sidebar_icon="mdi:calendar-clock",
            config={
                "js_url": "/tadiy/panel.js",
            },
            require_admin=False,
        )
        _LOGGER.info("TaDIY: Registered custom panel in sidebar")

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
        available_modes = hub_coordinator.get_custom_modes()

        if mode not in available_modes:
            _LOGGER.error("Invalid mode: %s (available: %s)", mode, available_modes)
            return

        hub_coordinator.set_hub_mode(mode)
        await hub_coordinator.async_save_schedules()
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

    async def handle_get_schedule(call: ServiceCall) -> dict:
        """Get schedule for a room."""
        from .schedule_storage import ScheduleStorageManager
        from .const import SCHEDULE_TYPE_DAILY, SCHEDULE_TYPE_WEEKDAY, SCHEDULE_TYPE_WEEKEND

        entity_id = call.data.get(ATTR_ENTITY_ID)
        mode = call.data.get(ATTR_MODE)
        schedule_type = call.data.get(ATTR_SCHEDULE_TYPE, SCHEDULE_TYPE_DAILY)

        # Find room coordinator by entity_id
        room_coord = None
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("type") == "room":
                # Check if this room has the entity
                if f"climate.{data['entry'].data.get(CONF_ROOM_NAME, '').lower().replace(' ', '_')}" == entity_id:
                    room_coord = data["coordinator"]
                    break

        if not room_coord or not room_coord.schedule_engine:
            _LOGGER.error("Room not found for entity: %s", entity_id)
            return {"blocks": []}

        room_name = room_coord.room_config.room_name
        room_schedule = room_coord.schedule_engine._room_schedules.get(room_name)

        if not room_schedule:
            # Return default schedule
            return {"blocks": ScheduleStorageManager.create_default_schedule(schedule_type)}

        # Get day schedule based on mode and type
        day_schedule = None
        if mode == "normal":
            if schedule_type == SCHEDULE_TYPE_WEEKDAY:
                day_schedule = room_schedule.normal_weekday
            elif schedule_type == SCHEDULE_TYPE_WEEKEND:
                day_schedule = room_schedule.normal_weekend
        elif mode == "homeoffice":
            day_schedule = room_schedule.homeoffice_daily
        else:
            day_schedule = room_schedule.get_custom_schedule(mode)

        if day_schedule:
            ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(day_schedule.blocks)
            return {"blocks": [b.to_dict() for b in ui_blocks]}

        return {"blocks": ScheduleStorageManager.create_default_schedule(schedule_type)}

    async def handle_set_schedule(call: ServiceCall) -> None:
        """Set schedule for a room."""
        from .schedule_storage import ScheduleStorageManager, ScheduleUIBlock
        from .core.schedule_model import DaySchedule
        from .const import SCHEDULE_TYPE_WEEKDAY, SCHEDULE_TYPE_WEEKEND

        entity_id = call.data.get(ATTR_ENTITY_ID)
        mode = call.data.get(ATTR_MODE)
        schedule_type = call.data.get(ATTR_SCHEDULE_TYPE, "daily")
        blocks_data = call.data.get(ATTR_BLOCKS)

        # Find room coordinator
        room_coord = None
        for entry_id, data in hass.data[DOMAIN].items():
            if data.get("type") == "room":
                if f"climate.{data['entry'].data.get(CONF_ROOM_NAME, '').lower().replace(' ', '_')}" == entity_id:
                    room_coord = data["coordinator"]
                    break

        if not room_coord or not room_coord.schedule_engine:
            _LOGGER.error("Room not found for entity: %s", entity_id)
            return

        # Convert to UI blocks and validate
        ui_blocks = [ScheduleUIBlock.from_dict(b) for b in blocks_data]
        is_valid, error = ScheduleStorageManager.validate_ui_blocks(ui_blocks)

        if not is_valid:
            _LOGGER.error("Invalid schedule blocks: %s", error)
            return

        # Convert to schedule blocks
        schedule_blocks = ScheduleStorageManager.ui_blocks_to_schedule_blocks(ui_blocks)
        day_schedule = DaySchedule(blocks=schedule_blocks)

        # Update room schedule
        room_name = room_coord.room_config.room_name
        room_schedule = room_coord.schedule_engine._room_schedules.get(room_name)

        if not room_schedule:
            from .core.schedule_model import RoomSchedule
            room_schedule = RoomSchedule(room_name=room_name)
            room_coord.schedule_engine._room_schedules[room_name] = room_schedule

        # Set the schedule based on mode and type
        if mode == "normal":
            if schedule_type == SCHEDULE_TYPE_WEEKDAY:
                room_schedule.normal_weekday = day_schedule
            elif schedule_type == SCHEDULE_TYPE_WEEKEND:
                room_schedule.normal_weekend = day_schedule
        elif mode == "homeoffice":
            room_schedule.homeoffice_daily = day_schedule
        else:
            room_schedule.set_custom_schedule(mode, day_schedule)

        # Save and refresh
        await room_coord.async_save_schedules()
        await room_coord.async_request_refresh()
        _LOGGER.info("Schedule updated for %s - %s/%s", room_name, mode, schedule_type)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_REFRESH, handle_force_refresh)
    hass.services.async_register(DOMAIN, SERVICE_RESET_LEARNING, handle_reset_learning, schema=SERVICE_RESET_LEARNING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BOOST_ALL_ROOMS, handle_boost_all_rooms, schema=SERVICE_BOOST_ALL_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_HUB_MODE, handle_set_hub_mode, schema=SERVICE_SET_HUB_MODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_HEATING_CURVE, handle_set_heating_curve, schema=SERVICE_SET_HEATING_CURVE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_GET_SCHEDULE, handle_get_schedule, schema=SERVICE_GET_SCHEDULE_SCHEMA, supports_response=True)
    hass.services.async_register(DOMAIN, SERVICE_SET_SCHEDULE, handle_set_schedule, schema=SERVICE_SET_SCHEDULE_SCHEMA)


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
            hass.services.async_remove(DOMAIN, SERVICE_GET_SCHEDULE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_SCHEDULE)
            hass.data[DOMAIN].pop("hub_coordinator", None)
            # Remove custom panel from sidebar
            try:
                from homeassistant.components import frontend
                await frontend.async_remove_panel(hass, "tadiy-schedules")
                _LOGGER.info("TaDIY: Removed custom panel from sidebar")
            except Exception as err:
                _LOGGER.warning("Failed to remove TaDIY panel: %s", err)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)