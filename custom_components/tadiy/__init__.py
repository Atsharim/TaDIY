"""The TaDIY integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_BLOCKS,
    ATTR_DURATION_MINUTES,
    ATTR_ENTITY_ID,
    ATTR_HEATING_RATE,
    ATTR_LOCATION_OVERRIDE,
    ATTR_MODE,
    ATTR_OFFSET,
    ATTR_ROOM,
    ATTR_SCHEDULE_TYPE,
    ATTR_TEMPERATURE,
    CONF_ADJACENT_ROOMS,
    CONF_AWAY_TEMPERATURE,
    CONF_BOILER_MIN_RUN_TIME,
    CONF_BOILER_TEMP_SENSOR,
    CONF_BOOST_DURATION,
    CONF_BOOST_TEMPERATURE,
    CONF_DEBUG_CALIBRATION,
    CONF_DEBUG_CARDS,
    CONF_DEBUG_EARLY_START,
    CONF_DEBUG_HEATING,
    CONF_DEBUG_HUB,
    CONF_DEBUG_PANEL,
    CONF_DEBUG_ROOMS,
    CONF_DEBUG_SCHEDULE,
    CONF_DEBUG_SENSORS,
    CONF_DEBUG_TRV,
    CONF_DEBUG_UI,
    CONF_DEBUG_VERBOSE,
    CONF_CYCLE_LOCK_ON_SETPOINT_DROP,
    CONF_DHW_TEMP_SENSOR,
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_EARLY_START_MAX,
    CONF_FROST_PROTECTION_TEMP,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_OFFSET_DURATION_HOURS,
    CONF_GLOBAL_OFFSET_MODE,
    CONF_GLOBAL_OFFSET_STEP,
    CONF_GLOBAL_OVERRIDE_TIMEOUT,
    CONF_HUB,
    CONF_PERSON_ENTITIES,
    CONF_ROOM_NAME,
    CONF_SHOW_PANEL,
    CONF_TOLERANCE,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_HOUSE_SETBACK_DELTA,
    CONF_WINDOW_NEIGHBOR_SETBACK_DELTA,
    CONF_WINDOW_NEIGHBOR_SETBACK_ENABLED,
    CONF_WINDOW_OPEN_TIMEOUT,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMPERATURE,
    DOMAIN,
    MAX_BOOST_DURATION,
    MAX_BOOST_TEMP,
    MAX_HEATING_RATE,
    MAX_TRV_OFFSET,
    MIN_BOOST_DURATION,
    MIN_BOOST_TEMP,
    MIN_HEATING_RATE,
    MIN_TRV_OFFSET,
    SERVICE_APPLY_PID_AUTOTUNE,
    SERVICE_BOOST_ALL_ROOMS,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_FORCE_REFRESH,
    SERVICE_GET_SCHEDULE,
    SERVICE_REFRESH_WEATHER_FORECAST,
    SERVICE_RESET_LEARNING,
    SERVICE_SET_HEATING_CURVE,
    SERVICE_SET_HOMEOFFICE_TOMORROW,
    SERVICE_SET_GLOBAL_OFFSET,
    SERVICE_SET_HUB_CONFIG,
    SERVICE_SET_HUB_MODE,
    SERVICE_SET_LOCATION_OVERRIDE,
    SERVICE_SET_ROOM_CONFIG,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_TRV_CALIBRATION,
    SERVICE_START_PID_AUTOTUNE,
    SERVICE_STOP_PID_AUTOTUNE,
)
from .coordinator import TaDIYHubCoordinator, TaDIYRoomCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_DEBUG_KEYS = [
    CONF_DEBUG_ROOMS,
    CONF_DEBUG_HUB,
    CONF_DEBUG_PANEL,
    CONF_DEBUG_UI,
    CONF_DEBUG_CARDS,
    CONF_DEBUG_TRV,
    CONF_DEBUG_SENSORS,
    CONF_DEBUG_SCHEDULE,
    CONF_DEBUG_VERBOSE,
    CONF_DEBUG_HEATING,
    CONF_DEBUG_CALIBRATION,
    CONF_DEBUG_EARLY_START,
]


def _apply_debug_settings(config_data: dict) -> None:
    """Apply debug settings from hub config to Python logger level.

    When any hub debug flag is enabled, set the TaDIY logger to DEBUG.
    When all flags are disabled, set it to INFO so standard operational logs remain visible.
    """
    tadiy_logger = logging.getLogger("custom_components.tadiy")
    any_debug = any(config_data.get(key, False) for key in _DEBUG_KEYS)
    if any_debug:
        tadiy_logger.setLevel(logging.DEBUG)
    else:
        tadiy_logger.setLevel(logging.INFO)


SERVICE_RESET_LEARNING_SCHEMA = vol.Schema({vol.Optional(ATTR_ROOM): cv.string})
SERVICE_BOOST_ALL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TEMPERATURE, default=DEFAULT_BOOST_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_BOOST_TEMP, max=MAX_BOOST_TEMP)
        ),
        vol.Optional(ATTR_DURATION_MINUTES, default=DEFAULT_BOOST_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_BOOST_DURATION, max=MAX_BOOST_DURATION)
        ),
    }
)
SERVICE_SET_HUB_MODE_SCHEMA = vol.Schema({vol.Required(ATTR_MODE): cv.string})
SERVICE_SET_HEATING_CURVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM): cv.string,
        vol.Required(ATTR_HEATING_RATE): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_HEATING_RATE, max=MAX_HEATING_RATE)
        ),
    }
)
SERVICE_GET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_MODE): cv.string,
        vol.Optional(ATTR_SCHEDULE_TYPE): cv.string,
    }
)
SERVICE_SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_MODE): cv.string,
        vol.Optional(ATTR_SCHEDULE_TYPE): cv.string,
        vol.Required(ATTR_BLOCKS): vol.All(cv.ensure_list, [dict]),
    }
)
SERVICE_SET_TRV_CALIBRATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_MODE): vol.In(["auto", "manual", "disabled"]),
        vol.Optional(ATTR_OFFSET): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_TRV_OFFSET, max=MAX_TRV_OFFSET)
        ),
    }
)
SERVICE_CLEAR_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ROOM): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)
SERVICE_SET_LOCATION_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOCATION_OVERRIDE): vol.In(["auto", "home", "away"]),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TaDIY component."""
    hass.data.setdefault(DOMAIN, {})

    # Register static file routes for Lovelace cards and panel (individual file routes avoid
    # conflicting with the /tadiy frontend panel route, preventing 403 Forbidden on /tadiy)
    files_path = Path(__file__).parent / "www"
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/tadiy/tadiy-panel.js",
                    str(files_path / "tadiy-panel.js"),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/tadiy/tadiy-schedule-card.js",
                    str(files_path / "tadiy-schedule-card.js"),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/tadiy/tadiy-overview-card.js",
                    str(files_path / "tadiy-overview-card.js"),
                    cache_headers=False,
                ),
            ]
        )
        _LOGGER.info("TaDIY: Registered static file paths for Lovelace cards")
    except ValueError as err:
        # Path already registered (can happen during reload)
        _LOGGER.debug("TaDIY: Static paths already registered: %s", err)

    return True


async def async_register_lovelace_resources(hass: HomeAssistant) -> None:
    """Log instructions for registering Lovelace resources."""
    from .const import VERSION

    # Note: Home Assistant doesn't allow automatic registration of Lovelace resources
    # for security reasons. Users must add them manually.

    _LOGGER.info(
        "\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "  TaDIY Cards Setup Required\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "\n"
        "To use TaDIY cards in your Lovelace dashboards:\n"
        "\n"
        "1. Go to Settings → Dashboards → Resources (⋮ menu → Resources)\n"
        "2. Click '+ ADD RESOURCE' and add BOTH:\n"
        "\n"
        "   Schedule Card (for editing schedules):\n"
        "   URL: /tadiy/tadiy-schedule-card.js\n"
        "   Type: JavaScript Module\n"
        "\n"
        "   Overview Card (panel view for dashboards):\n"
        "   URL: /tadiy/tadiy-overview-card.js\n"
        "   Type: JavaScript Module\n"
        "\n"
        "   Note: Version parameter (?v=%s) is optional for cache busting.\n"
        "   Without it, use Ctrl+F5 to reload after updates.\n"
        "\n"
        "3. Usage in dashboards:\n"
        "\n"
        "   Schedule Editor:\n"
        "     type: custom:tadiy-schedule-card\n"
        "     entity: climate.your_room\n"
        "\n"
        "   Overview (all rooms):\n"
        "     type: custom:tadiy-overview-card\n"
        "\n"
        "The TaDIY Panel is already available in the sidebar!\n"
        "═══════════════════════════════════════════════════════════════════\n",
        VERSION,
    )


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

    # Ensure static file paths are registered (in case async_setup wasn't called)
    files_path = Path(__file__).parent / "www"
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/tadiy/tadiy-panel.js",
                    str(files_path / "tadiy-panel.js"),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/tadiy/tadiy-schedule-card.js",
                    str(files_path / "tadiy-schedule-card.js"),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/tadiy/tadiy-overview-card.js",
                    str(files_path / "tadiy-overview-card.js"),
                    cache_headers=False,
                ),
            ]
        )
        _LOGGER.debug("TaDIY: Static file paths ensured during hub setup")
    except ValueError:
        # Path already registered, that's fine
        pass

    hub_coordinator = TaDIYHubCoordinator(hass, entry.entry_id, entry.data, entry)
    await hub_coordinator.async_load_learning_data()
    await hub_coordinator.async_load_schedules()
    await hub_coordinator.async_load_location_data()
    await hub_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN]["hub_coordinator"] = hub_coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": hub_coordinator,
        "type": "hub",
        "entry": entry,
    }

    # Update hub_coordinator reference on all existing room coordinators (e.g. after hub reload)
    for item in hass.data[DOMAIN].values():
        if isinstance(item, dict) and item.get("type") == "room":
            room_coord = item.get("coordinator")
            if room_coord:
                room_coord.hub_coordinator = hub_coordinator

    # Apply debug settings from hub config
    _apply_debug_settings(entry.data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await async_register_services(hass, hub_coordinator, entry)

    # Register Lovelace resources for cards
    await async_register_lovelace_resources(hass)

    # Register custom panel (only if enabled in config)
    show_panel = entry.data.get(CONF_SHOW_PANEL, True)
    if show_panel:
        from .panel import async_register_panel

        # Register the panel
        await async_register_panel(hass)
        _LOGGER.info("TaDIY panel registered")
    else:
        _LOGGER.info("TaDIY panel disabled in config")

    _LOGGER.info("TaDIY Hub setup complete")

    return True


async def async_setup_room(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY Room."""
    import asyncio

    room_name = entry.data.get(CONF_ROOM_NAME, "Unknown")
    _LOGGER.info("Setting up TaDIY Room: %s", room_name)

    # Wait for hub coordinator with retries (max 10 seconds)
    hub_coordinator = None
    for _ in range(20):  # 20 attempts * 0.5s = 10 seconds max
        hub_coordinator = hass.data[DOMAIN].get("hub_coordinator")
        if hub_coordinator:
            break
        _LOGGER.debug("Waiting for hub coordinator... (room: %s)", room_name)
        await asyncio.sleep(0.5)

    if not hub_coordinator:
        _LOGGER.warning(
            "Hub coordinator not found for room setup after timeout, retrying later"
        )
        raise ConfigEntryNotReady("Hub coordinator not found")

    room_coordinator = TaDIYRoomCoordinator(
        hass, entry.entry_id, entry.data, hub_coordinator
    )
    await room_coordinator.async_load_schedules()
    await room_coordinator.async_load_heat_model()
    await room_coordinator.async_load_calibrations()
    await room_coordinator.async_load_overrides()
    await room_coordinator.async_load_feature_settings()
    await room_coordinator.async_load_thermal_mass()
    await room_coordinator.async_load_overshoot()
    await room_coordinator.async_load_heating_stats()
    await room_coordinator.async_load_savings_stats()
    await room_coordinator.async_load_valve_protection()
    await room_coordinator.async_config_entry_first_refresh()

    # Set up state listeners for override detection
    room_coordinator.setup_state_listeners()

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
        from .core.early_start import EarlyStartCalculator, HeatUpModel

        room_name = call.data.get(ATTR_ROOM)
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if room_name and room_coord.room_config.name != room_name:
                    continue
                new_model = HeatUpModel(room_name=room_coord.room_config.name)
                new_model.set_debug_callback(room_coord._debug_callback)
                room_coord._heat_model = new_model
                room_coord.early_start_calculator = EarlyStartCalculator(
                    new_model, debug_callback=room_coord._debug_callback
                )
                hub_coordinator.register_heat_model(
                    room_coord.room_config.name, new_model
                )
                await room_coord.async_save_heat_model()
                await room_coord.async_request_refresh()
        await hub_coordinator.async_save_learning_data()
        _LOGGER.info(
            "Learning data reset for %s", f"room: {room_name}" if room_name else "all rooms"
        )

    async def handle_boost_all_rooms(call: ServiceCall) -> None:
        temperature = call.data.get(ATTR_TEMPERATURE, DEFAULT_BOOST_TEMPERATURE)

        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
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
            if isinstance(data, dict) and data.get("type") == "room":
                await data["coordinator"].async_request_refresh()

    async def handle_set_homeoffice_tomorrow(call: ServiceCall) -> None:
        enabled = call.data.get("enabled", True)
        if hasattr(hub_coordinator, "set_homeoffice_tomorrow"):
            hub_coordinator.set_homeoffice_tomorrow(enabled)
            await hub_coordinator.async_request_refresh()

    async def handle_set_heating_curve(call: ServiceCall) -> None:
        room_name = call.data.get(ATTR_ROOM)
        heating_rate = call.data.get(ATTR_HEATING_RATE)

        found = False
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if room_coord.room_config.name == room_name:
                    room_coord._heat_model.set_manual_rate(heating_rate)
                    await room_coord.async_save_heat_model()
                    await room_coord.async_request_refresh()
                    found = True
                    break

        if found or room_name in hub_coordinator.heat_models:
            if room_name in hub_coordinator.heat_models:
                hub_coordinator.heat_models[room_name].set_manual_rate(heating_rate)
            await hub_coordinator.async_save_learning_data()
            _LOGGER.info(
                "Heating rate for room %s set to %.2f °C/h", room_name, heating_rate
            )
        else:
            _LOGGER.error("Room not found: %s", room_name)

    async def handle_get_schedule(call: ServiceCall) -> dict:
        """Get schedule for a room."""
        from .const import (
            SCHEDULE_TYPE_DAILY,
            SCHEDULE_TYPE_WEEKDAY,
            SCHEDULE_TYPE_WEEKEND,
        )
        from .schedule_storage import ScheduleStorageManager

        entity_id = call.data.get(ATTR_ENTITY_ID)
        mode = call.data.get(ATTR_MODE)
        schedule_type = call.data.get(ATTR_SCHEDULE_TYPE, SCHEDULE_TYPE_DAILY)

        # Find room coordinator by entity_id
        room_coord = None
        entity_registry = er.async_get(hass)
        for data_entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                # Check if this room has the entity - match by unique_id pattern
                expected_unique_id = f"{data_entry_id}_climate"
                entity_entry = entity_registry.async_get(entity_id)

                if entity_entry and entity_entry.unique_id == expected_unique_id:
                    room_coord = data["coordinator"]
                    break

        if not room_coord or not room_coord.schedule_engine:
            _LOGGER.error("Room not found for entity: %s", entity_id)
            return {"blocks": []}

        room_name = room_coord.room_config.name
        room_schedule = room_coord.schedule_engine._room_schedules.get(room_name)

        if not room_schedule:
            # Return default schedule
            default_blocks = ScheduleStorageManager.create_default_schedule(
                schedule_type
            )
            return {"blocks": [b.to_dict() for b in default_blocks]}

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
            ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                day_schedule.blocks
            )
            return {"blocks": [b.to_dict() for b in ui_blocks]}

        # Fallback to default schedule
        default_blocks = ScheduleStorageManager.create_default_schedule(schedule_type)
        return {"blocks": [b.to_dict() for b in default_blocks]}

    async def handle_set_schedule(call: ServiceCall) -> None:
        """Set schedule for a room."""
        from .const import SCHEDULE_TYPE_WEEKDAY, SCHEDULE_TYPE_WEEKEND
        from .core.schedule_model import DaySchedule
        from .schedule_storage import ScheduleStorageManager, ScheduleUIBlock

        entity_id = call.data.get(ATTR_ENTITY_ID)
        mode = call.data.get(ATTR_MODE)
        schedule_type = call.data.get(ATTR_SCHEDULE_TYPE, "daily")
        blocks_data = call.data.get(ATTR_BLOCKS)

        # Find room coordinator
        room_coord = None
        entity_registry = er.async_get(hass)
        for data_entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                # Check if this room has the entity - match by unique_id pattern
                expected_unique_id = f"{data_entry_id}_climate"
                entity_entry = entity_registry.async_get(entity_id)

                if entity_entry and entity_entry.unique_id == expected_unique_id:
                    room_coord = data["coordinator"]
                    break

        if not room_coord or not room_coord.schedule_engine:
            _LOGGER.error("Room not found for entity: %s", entity_id)
            return

        room_name = room_coord.room_config.name

        # Convert to UI blocks and validate
        ui_blocks = [ScheduleUIBlock.from_dict(b) for b in blocks_data]
        is_valid, error = ScheduleStorageManager.validate_ui_blocks(ui_blocks)

        if not is_valid:
            _LOGGER.error("Invalid schedule blocks: %s", error)
            return

        # Convert to schedule blocks
        schedule_blocks = ScheduleStorageManager.ui_blocks_to_schedule_blocks(ui_blocks)
        day_schedule = DaySchedule(schedule_type=schedule_type, blocks=schedule_blocks)

        # Update room schedule
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

        # Clear any next_block/always overrides and force immediate target application
        for trv_id, override in list(room_coord.override_manager._overrides.items()):
            if override.timeout_mode in ("next_block", "always"):
                room_coord.override_manager.clear_override(trv_id)
        room_coord.trv_manager._last_applied_target = None

        # Save and refresh
        await room_coord.async_save_schedules()
        await room_coord.async_save_overrides()
        await room_coord.async_request_refresh()
        _LOGGER.info("Schedule updated for %s - %s/%s", room_name, mode, schedule_type)

    async def handle_set_trv_calibration(call: ServiceCall) -> None:
        """Set TRV calibration mode/offset/multiplier."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        mode = call.data.get(ATTR_MODE)
        offset = call.data.get(ATTR_OFFSET)
        offset = call.data.get(ATTR_OFFSET)

        # Find room coordinator that manages this TRV
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if entity_id in room_coord.room_config.trv_entity_ids:
                    cal_mgr = room_coord.calibration_manager

                    # Update mode
                    if mode:
                        cal_mgr.set_mode(entity_id, mode)

                    # Update offset (manual mode)
                    if offset is not None:
                        cal_mgr.set_manual_offset(entity_id, offset)

                    await room_coord.async_save_calibrations()
                    _LOGGER.info("TRV calibration updated for %s", entity_id)
                    return

        _LOGGER.error("TRV %s not found in any room", entity_id)

    async def handle_clear_override(call: ServiceCall) -> None:
        """Clear manual temperature overrides."""
        room_name = call.data.get(ATTR_ROOM)
        entity_id = call.data.get(ATTR_ENTITY_ID)

        if not room_name and not entity_id:
            _LOGGER.error("Must specify either room or entity_id")
            return

        cleared_count = 0

        # Find room coordinator(s)
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]

                # Check if this is the target room (if room_name specified)
                if room_name and room_coord.room_config.name != room_name:
                    continue

                # If entity_id specified, only clear that specific override
                if entity_id:
                    # Check if it is a TRV
                    if entity_id in room_coord.room_config.trv_entity_ids:
                        if room_coord.override_manager.clear_override(entity_id):
                            cleared_count += 1
                            await room_coord.async_save_overrides()
                            _LOGGER.info("Cleared override for %s", entity_id)

                    # Check if it is the Room Climate Entity
                    else:
                        entity_registry = er.async_get(hass)
                        entity_entry = entity_registry.async_get(entity_id)
                        expected_unique_id = f"{entry_id}_climate"

                        if (
                            entity_entry
                            and entity_entry.unique_id == expected_unique_id
                        ):
                            # User targeted the Room Entity -> Clear ALL overrides for this room
                            count = room_coord.override_manager.clear_all_overrides()
                            if count > 0:
                                cleared_count += count
                                await room_coord.async_save_overrides()
                                _LOGGER.info(
                                    "Cleared %d override(s) for room %s (via room entity)",
                                    count,
                                    room_coord.room_config.name,
                                )
                            # If count is 0, we still found the room, so we can stop searching if we want,
                            # or just continue.
                            return  # We found the target
                else:
                    # No entity_id, clear all for this room (if room_name matched)
                    count = room_coord.override_manager.clear_all_overrides()
                    if count > 0:
                        cleared_count += count
                        await room_coord.async_save_overrides()
                        _LOGGER.info(
                            "Cleared %d override(s) for room %s",
                            count,
                            room_coord.room_config.name,
                        )

                # If entity_id was specified and found (as TRV), stop searching
                if entity_id and cleared_count > 0:
                    return

        if cleared_count == 0:
            if entity_id:
                _LOGGER.warning("No override found for entity %s", entity_id)
            elif room_name:
                _LOGGER.warning("No overrides found for room %s", room_name)
        else:
            _LOGGER.info("Cleared %d override(s) total", cleared_count)

    async def handle_set_location_override(call: ServiceCall) -> None:
        """Set location override (auto/home/away)."""
        location_override = call.data.get(ATTR_LOCATION_OVERRIDE)

        # Find hub coordinator
        hub_coordinator = hass.data[DOMAIN].get("hub_coordinator")
        if not hub_coordinator:
            _LOGGER.error("Hub coordinator not found")
            return

        # Map string to boolean override
        if location_override == "auto":
            override_value = None
        elif location_override == "home":
            override_value = True
        elif location_override == "away":
            override_value = False
        else:
            _LOGGER.error("Invalid location override: %s", location_override)
            return

        hub_coordinator.set_location_override(override_value)
        _LOGGER.info("Location override set to: %s", location_override)

        # Request refresh to apply changes immediately
        await hub_coordinator.async_request_refresh()

    async def handle_start_pid_autotune(call: ServiceCall) -> None:
        """Start PID auto-tuning for a room."""
        room_name = call.data.get(ATTR_ROOM)

        # Find room coordinator
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if room_coord.room_config.name == room_name:
                    # Check if PID control is enabled
                    if not room_coord.room_config.use_pid_control:
                        _LOGGER.error(
                            "Cannot start PID auto-tuning for room %s: PID control is disabled",
                            room_name,
                        )
                        return

                    room_coord.pid_autotuner.start_tuning()
                    _LOGGER.info("Started PID auto-tuning for room %s", room_name)
                    return

        _LOGGER.error("Room %s not found", room_name)

    async def handle_stop_pid_autotune(call: ServiceCall) -> None:
        """Stop PID auto-tuning for a room."""
        room_name = call.data.get(ATTR_ROOM)

        # Find room coordinator
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if room_coord.room_config.name == room_name:
                    room_coord.pid_autotuner.stop_tuning()
                    _LOGGER.info("Stopped PID auto-tuning for room %s", room_name)
                    return

        _LOGGER.error("Room %s not found", room_name)

    async def handle_apply_pid_autotune(call: ServiceCall) -> None:
        """Apply auto-tuned PID parameters to a room."""
        room_name = call.data.get(ATTR_ROOM)

        # Find room coordinator
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and data.get("type") == "room":
                room_coord = data["coordinator"]
                if room_coord.room_config.name == room_name:
                    # Get tuned parameters
                    params = room_coord.pid_autotuner.get_tuned_parameters()
                    if not params:
                        _LOGGER.error(
                            "No tuned parameters available for room %s (tuning not complete)",
                            room_name,
                        )
                        return

                    kp, ki, kd = params

                    # Apply to PID controller
                    from .core.control import PIDHeatingController

                    if isinstance(room_coord.heating_controller, PIDHeatingController):
                        room_coord.heating_controller.config.kp = kp
                        room_coord.heating_controller.config.ki = ki
                        room_coord.heating_controller.config.kd = kd
                        room_coord.heating_controller.reset()

                        # Save to storage
                        await room_coord.async_save_feature_settings()

                        _LOGGER.info(
                            "Applied auto-tuned PID parameters to room %s: Kp=%.3f, Ki=%.4f, Kd=%.3f",
                            room_name,
                            kp,
                            ki,
                            kd,
                        )
                    else:
                        _LOGGER.error(
                            "Room %s does not use PID controller",
                            room_name,
                        )
                    return

        _LOGGER.error("Room %s not found", room_name)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_REFRESH, handle_force_refresh)
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOMEOFFICE_TOMORROW,
        handle_set_homeoffice_tomorrow,
        schema=vol.Schema({vol.Optional("enabled", default=True): cv.boolean}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEATING_CURVE,
        handle_set_heating_curve,
        schema=SERVICE_SET_HEATING_CURVE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SCHEDULE,
        handle_get_schedule,
        schema=SERVICE_GET_SCHEDULE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        handle_set_schedule,
        schema=SERVICE_SET_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TRV_CALIBRATION,
        handle_set_trv_calibration,
        schema=SERVICE_SET_TRV_CALIBRATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_OVERRIDE,
        handle_clear_override,
        schema=SERVICE_CLEAR_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCATION_OVERRIDE,
        handle_set_location_override,
        schema=SERVICE_SET_LOCATION_OVERRIDE_SCHEMA,
    )

    # PID Auto-Tuning services
    SERVICE_START_PID_AUTOTUNE_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})
    SERVICE_STOP_PID_AUTOTUNE_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})
    SERVICE_APPLY_PID_AUTOTUNE_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_PID_AUTOTUNE,
        handle_start_pid_autotune,
        schema=SERVICE_START_PID_AUTOTUNE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_PID_AUTOTUNE,
        handle_stop_pid_autotune,
        schema=SERVICE_STOP_PID_AUTOTUNE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PID_AUTOTUNE,
        handle_apply_pid_autotune,
        schema=SERVICE_APPLY_PID_AUTOTUNE_SCHEMA,
    )

    # Weather Prediction service
    async def handle_refresh_weather_forecast(call: ServiceCall) -> None:
        """Refresh weather forecast manually."""
        success = await hub_coordinator.async_refresh_weather_forecast()
        if success:
            _LOGGER.info("Weather forecast refreshed successfully")
        else:
            _LOGGER.warning(
                "Weather forecast refresh failed or no weather entity configured"
            )

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH_WEATHER_FORECAST, handle_refresh_weather_forecast
    )

    # Hub configuration service (allows adjusting Hub settings directly from UI panel)
    SERVICE_SET_HUB_CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_FROST_PROTECTION_TEMP): vol.Coerce(float),
            vol.Optional(CONF_BOOST_TEMPERATURE): vol.Coerce(float),
            vol.Optional(CONF_BOOST_DURATION): cv.positive_int,
            vol.Optional(CONF_WINDOW_OPEN_TIMEOUT): cv.positive_int,
            vol.Optional(CONF_WINDOW_CLOSE_TIMEOUT): cv.positive_int,
            vol.Optional(CONF_GLOBAL_OVERRIDE_TIMEOUT): cv.positive_int,
            vol.Optional(CONF_DONT_HEAT_BELOW_OUTDOOR): vol.Any(None, vol.Coerce(float)),
            vol.Optional(CONF_BOILER_TEMP_SENSOR): cv.string,
            vol.Optional(CONF_DHW_TEMP_SENSOR): cv.string,
            vol.Optional(CONF_BOILER_MIN_RUN_TIME): cv.positive_int,
            vol.Optional(CONF_CYCLE_LOCK_ON_SETPOINT_DROP): cv.boolean,
            vol.Optional(CONF_PERSON_ENTITIES): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_WINDOW_NEIGHBOR_SETBACK_ENABLED): cv.boolean,
            vol.Optional(CONF_WINDOW_NEIGHBOR_SETBACK_DELTA): vol.Coerce(float),
            vol.Optional(CONF_WINDOW_HOUSE_SETBACK_DELTA): vol.Coerce(float),
            vol.Optional(CONF_GLOBAL_OFFSET_STEP): vol.Coerce(float),
            vol.Optional(CONF_GLOBAL_OFFSET_MODE): cv.string,
            vol.Optional(CONF_GLOBAL_OFFSET_DURATION_HOURS): vol.Coerce(float),
        }
    )

    async def handle_set_hub_config(call: ServiceCall) -> None:
        """Update hub configuration options dynamically."""
        hub_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("is_hub", False) or entry.data.get("entry_type") == "hub":
                hub_entry = entry
                break
        if not hub_entry:
            _LOGGER.error("Cannot set hub config: No hub entry found")
            return

        new_options = dict(hub_entry.options)
        for key in [
            CONF_FROST_PROTECTION_TEMP,
            CONF_BOOST_TEMPERATURE,
            CONF_BOOST_DURATION,
            CONF_WINDOW_OPEN_TIMEOUT,
            CONF_WINDOW_CLOSE_TIMEOUT,
            CONF_GLOBAL_OVERRIDE_TIMEOUT,
            CONF_DONT_HEAT_BELOW_OUTDOOR,
            CONF_BOILER_TEMP_SENSOR,
            CONF_DHW_TEMP_SENSOR,
            CONF_BOILER_MIN_RUN_TIME,
            CONF_CYCLE_LOCK_ON_SETPOINT_DROP,
            CONF_PERSON_ENTITIES,
            CONF_WINDOW_NEIGHBOR_SETBACK_ENABLED,
            CONF_WINDOW_NEIGHBOR_SETBACK_DELTA,
            CONF_WINDOW_HOUSE_SETBACK_DELTA,
            CONF_GLOBAL_OFFSET_STEP,
            CONF_GLOBAL_OFFSET_MODE,
            CONF_GLOBAL_OFFSET_DURATION_HOURS,
        ]:
            if key in call.data:
                val = call.data[key]
                if val is None:
                    new_options.pop(key, None)
                    if key == CONF_DONT_HEAT_BELOW_OUTDOOR:
                        new_options.pop(CONF_GLOBAL_DONT_HEAT_BELOW, None)
                else:
                    new_options[key] = val
                    if key == CONF_DONT_HEAT_BELOW_OUTDOOR:
                        new_options[CONF_GLOBAL_DONT_HEAT_BELOW] = val

        hass.config_entries.async_update_entry(hub_entry, options=new_options)
        # Apply immediately to running hub coordinator
        entry_data = hass.data.get(DOMAIN, {}).get(hub_entry.entry_id, {})
        coord = entry_data.get("coordinator") if isinstance(entry_data, dict) else None
        if coord:
            coord.config_data.update(new_options)
            coord._update_global_settings()
            coord.async_update_listeners()
        _LOGGER.info("Hub options updated via service: %s", call.data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HUB_CONFIG,
        handle_set_hub_config,
        schema=SERVICE_SET_HUB_CONFIG_SCHEMA,
    )

    # Global Quick Offset service (±X°C across all rooms)
    SERVICE_SET_GLOBAL_OFFSET_SCHEMA = vol.Schema(
        {
            vol.Required("offset"): vol.Coerce(float),
            vol.Optional("mode"): cv.string,
            vol.Optional("duration_hours"): vol.Coerce(float),
        }
    )

    async def handle_set_global_offset(call: ServiceCall) -> None:
        """Set or reset global quick offset across all rooms."""
        hub_coord = None
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and entry_data.get("type") == "hub":
                hub_coord = entry_data.get("coordinator")
                break
        if not hub_coord:
            _LOGGER.error("Cannot set global offset: No hub coordinator found")
            return

        offset = float(call.data["offset"])
        mode = call.data.get("mode")
        dur = call.data.get("duration_hours")
        await hub_coord.async_set_global_offset(offset, mode=mode, duration_hours=dur)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_GLOBAL_OFFSET,
        handle_set_global_offset,
        schema=SERVICE_SET_GLOBAL_OFFSET_SCHEMA,
    )

    # Room configuration service (allows adjusting Room settings directly from UI panel)
    SERVICE_SET_ROOM_CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required("entity_id"): cv.string,
            vol.Optional(CONF_AWAY_TEMPERATURE): vol.Coerce(float),
            vol.Optional("tolerance"): vol.Coerce(float),
            vol.Optional("early_start_max_minutes"): cv.positive_int,
            vol.Optional("window_open_timeout"): cv.positive_int,
            vol.Optional("window_close_timeout"): cv.positive_int,
            vol.Optional("dont_heat_below_outdoor"): vol.Any(None, vol.Coerce(float)),
            vol.Optional("min_heating_rate"): vol.Coerce(float),
            vol.Optional("max_heating_rate"): vol.Coerce(float),
            vol.Optional(CONF_ADJACENT_ROOMS): vol.All(cv.ensure_list, [cv.string]),
        }
    )

    async def handle_set_room_config(call: ServiceCall) -> None:
        """Update room configuration options dynamically."""
        entity_id = call.data.get("entity_id")
        room_entry = None
        matched_coordinator = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if not entry.data.get("is_hub", False) and entry.data.get("entry_type") != "hub":
                room_coord = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
                if room_coord:
                    climate_id = f"climate.{room_coord.room_config.name.lower().replace(' ', '_')}"
                    if (
                        climate_id == entity_id
                        or entry.entry_id == entity_id
                        or room_coord.room_config.name.lower() in entity_id.lower()
                    ):
                        room_entry = entry
                        matched_coordinator = room_coord
                        break
                elif entry.title.lower() in entity_id.lower() or entry.entry_id == entity_id:
                    room_entry = entry
                    break

        if not room_entry:
            _LOGGER.error("Cannot set room config: Room entry not found for %s", entity_id)
            return

        new_options = dict(room_entry.options)
        for key in [
            CONF_AWAY_TEMPERATURE,
            "tolerance",
            "early_start_max_minutes",
            "window_open_timeout",
            "window_close_timeout",
            "dont_heat_below_outdoor",
            "min_heating_rate",
            "max_heating_rate",
            CONF_ADJACENT_ROOMS,
        ]:
            if key in call.data:
                val = call.data[key]
                if val is None:
                    new_options.pop(key, None)
                else:
                    new_options[key] = val

        hass.config_entries.async_update_entry(room_entry, options=new_options)

        # Apply immediately to running room coordinator if available
        if matched_coordinator and hasattr(matched_coordinator, "room_config"):
            if CONF_AWAY_TEMPERATURE in call.data:
                matched_coordinator.room_config.away_temperature = call.data[CONF_AWAY_TEMPERATURE]
            if "tolerance" in call.data:
                matched_coordinator.room_config.tolerance = call.data["tolerance"]
            if "early_start_max_minutes" in call.data:
                matched_coordinator.room_config.early_start_max_minutes = call.data["early_start_max_minutes"]
            if "window_open_timeout" in call.data:
                matched_coordinator.room_config.window_open_timeout = call.data["window_open_timeout"]
            if "window_close_timeout" in call.data:
                matched_coordinator.room_config.window_close_timeout = call.data["window_close_timeout"]
            if "dont_heat_below_outdoor" in call.data:
                matched_coordinator.room_config.dont_heat_below_outdoor = call.data["dont_heat_below_outdoor"]
            if "min_heating_rate" in call.data:
                matched_coordinator.room_config.min_heating_rate = call.data["min_heating_rate"]
            if "max_heating_rate" in call.data:
                matched_coordinator.room_config.max_heating_rate = call.data["max_heating_rate"]
            if CONF_ADJACENT_ROOMS in call.data:
                matched_coordinator.room_config.adjacent_rooms = call.data[CONF_ADJACENT_ROOMS]
            matched_coordinator.async_update_listeners()

        _LOGGER.info("Room options updated via service for %s: %s", room_entry.title, call.data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROOM_CONFIG,
        handle_set_room_config,
        schema=SERVICE_SET_ROOM_CONFIG_SCHEMA,
    )


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
        await coordinator.async_save_calibrations()
        await coordinator.async_save_overrides()
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if entry_data.get("type") == "hub":
            # Unregister panel
            from .panel import async_unregister_panel

            await async_unregister_panel(hass)

            hass.services.async_remove(DOMAIN, SERVICE_FORCE_REFRESH)
            hass.services.async_remove(DOMAIN, SERVICE_RESET_LEARNING)
            hass.services.async_remove(DOMAIN, SERVICE_BOOST_ALL_ROOMS)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HUB_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HOMEOFFICE_TOMORROW)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HEATING_CURVE)
            hass.services.async_remove(DOMAIN, SERVICE_GET_SCHEDULE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_TRV_CALIBRATION)
            hass.services.async_remove(DOMAIN, SERVICE_SET_SCHEDULE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_HUB_CONFIG)
            hass.services.async_remove(DOMAIN, SERVICE_SET_ROOM_CONFIG)
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_OVERRIDE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_LOCATION_OVERRIDE)
            hass.data[DOMAIN].pop("hub_coordinator", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
