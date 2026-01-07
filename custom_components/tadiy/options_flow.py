"""Options flow for TaDIY."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_LEARN_HEATING_RATE,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_TARGET_TEMP_STEP,
    CONF_TOLERANCE,
    CONF_TRV_ENTITIES,
    CONF_USE_EARLY_START,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    TEMP_STEP_OPTIONS,
    TOLERANCE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def convert_seconds_to_duration(seconds: int) -> dict[str, int]:
    """Convert seconds to duration dict."""
    return {
        "hours": seconds // 3600,
        "minutes": (seconds % 3600) // 60,
        "seconds": seconds % 60,
    }


def convert_duration_to_seconds(duration: dict[str, int]) -> int:
    """Convert duration dict to seconds."""
    return (
        duration.get("hours", 0) * 3600
        + duration.get("minutes", 0) * 60
        + duration.get("seconds", 0)
    )


class TaDIYOptionsFlowHandler(OptionsFlow):
    """Handle TaDIY options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._current_room: dict[str, Any] | None = None
        self._room_index: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - main menu."""
        room_count = len(self.config_entry.options.get(CONF_ROOMS, []))
        
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "global_defaults",
                "add_room",
                "edit_room_select",
                "delete_room_select",
            ],
            description_placeholders={
                "room_count": str(room_count),
            },
        )

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit global defaults."""
        if user_input is not None:
            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_OPEN_TIMEOUT), dict):
                user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT]
                )

            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT), dict):
                user_input[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT]
                )

            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data=self.config_entry.options)

        current_global = self.config_entry.data
        
        window_open_val = current_global.get(
            CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
        )
        window_close_val = current_global.get(
            CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
        )

        window_open_default = (
            convert_seconds_to_duration(window_open_val)
            if isinstance(window_open_val, int)
            else window_open_val
        )
        window_close_default = (
            convert_seconds_to_duration(window_close_val)
            if isinstance(window_close_val, int)
            else window_close_val
        )

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                    default=window_open_default,
                ): selector.DurationSelector(
                    selector.DurationSelectorConfig(enable_day=False)
                ),
                vol.Optional(
                    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                    default=window_close_default,
                ): selector.DurationSelector(
                    selector.DurationSelectorConfig(enable_day=False)
                ),
                vol.Optional(
                    CONF_GLOBAL_DONT_HEAT_BELOW,
                    default=current_global.get(
                        CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10,
                        max=35,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_GLOBAL_USE_EARLY_START,
                    default=current_global.get(
                        CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START
                    ),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_GLOBAL_LEARN_HEATING_RATE,
                    default=current_global.get(
                        CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
                    ),
                ): selector.BooleanSelector(),
            }),
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        errors: dict[str, str] = {}

        if user_input is not None:
            existing_rooms = self.config_entry.options.get(CONF_ROOMS, [])
            room_names = [r.get(CONF_ROOM_NAME) for r in existing_rooms]

            if user_input[CONF_ROOM_NAME] in room_names:
                errors[CONF_ROOM_NAME] = "name_exists"
            else:
                self._convert_durations_to_seconds(user_input)
                new_rooms = existing_rooms + [user_input]
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, CONF_ROOMS: new_rooms}
                )

        return self.async_show_form(
            step_id="add_room",
            data_schema=self._room_schema(),
            errors=errors,
        )

    async def async_step_edit_room_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select room to edit."""
        rooms = self.config_entry.options.get(CONF_ROOMS, [])
        
        if not rooms:
            return self.async_abort(reason="no_rooms")

        if user_input is not None:
            room_name = user_input["room"]
            for idx, room in enumerate(rooms):
                if room.get(CONF_ROOM_NAME) == room_name:
                    self._current_room = room
                    self._room_index = idx
                    return await self.async_step_edit_room()
            return self.async_abort(reason="invalid_room")

        room_names = [r.get(CONF_ROOM_NAME, f"Room {i}") for i, r in enumerate(rooms)]
        
        return self.async_show_form(
            step_id="edit_room_select",
            data_schema=vol.Schema({
                vol.Required("room"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=room_names,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_edit_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing room."""
        if user_input is not None:
            self._convert_durations_to_seconds(user_input)
            rooms = self.config_entry.options.get(CONF_ROOMS, [])
            rooms[self._room_index] = user_input
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_ROOMS: rooms}
            )

        return self.async_show_form(
            step_id="edit_room",
            data_schema=self._room_schema(self._current_room),
            description_placeholders={
                "room_name": self._current_room.get(CONF_ROOM_NAME, "Unknown"),
            },
        )

    async def async_step_delete_room_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select room to delete."""
        rooms = self.config_entry.options.get(CONF_ROOMS, [])
        
        if not rooms:
            return self.async_abort(reason="no_rooms")

        if user_input is not None:
            room_name = user_input["room"]
            new_rooms = [r for r in rooms if r.get(CONF_ROOM_NAME) != room_name]
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_ROOMS: new_rooms}
            )

        room_names = [r.get(CONF_ROOM_NAME, f"Room {i}") for i, r in enumerate(rooms)]
        
        return self.async_show_form(
            step_id="delete_room_select",
            data_schema=vol.Schema({
                vol.Required("room"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=room_names,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    def _convert_durations_to_seconds(self, data: dict[str, Any]) -> None:
        """Convert duration dicts to seconds in place."""
        if isinstance(data.get(CONF_WINDOW_OPEN_TIMEOUT), dict):
            data[CONF_WINDOW_OPEN_TIMEOUT] = convert_duration_to_seconds(
                data[CONF_WINDOW_OPEN_TIMEOUT]
            )

        if isinstance(data.get(CONF_WINDOW_CLOSE_TIMEOUT), dict):
            data[CONF_WINDOW_CLOSE_TIMEOUT] = convert_duration_to_seconds(
                data[CONF_WINDOW_CLOSE_TIMEOUT]
            )

    def _get_global_default(self, key: str, default: Any) -> Any:
        """Get global default from config entry data."""
        global_key = f"global_{key}"
        return self.config_entry.data.get(global_key, default)

    def _room_schema(self, room_data: dict[str, Any] | None = None) -> vol.Schema:
        """Generate room configuration schema with global defaults."""
        global_window_open = self._get_global_default(
            CONF_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
        )
        global_window_close = self._get_global_default(
            CONF_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
        )
        global_dont_heat = self._get_global_default(
            CONF_DONT_HEAT_BELOW_OUTDOOR, DEFAULT_DONT_HEAT_BELOW
        )
        global_early_start = self._get_global_default(
            CONF_USE_EARLY_START, DEFAULT_USE_EARLY_START
        )
        global_learn = self._get_global_default(
            CONF_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
        )

        window_open_val = (
            room_data.get(CONF_WINDOW_OPEN_TIMEOUT, global_window_open)
            if room_data
            else global_window_open
        )
        window_close_val = (
            room_data.get(CONF_WINDOW_CLOSE_TIMEOUT, global_window_close)
            if room_data
            else global_window_close
        )

        window_open_default = (
            convert_seconds_to_duration(window_open_val)
            if isinstance(window_open_val, int)
            else window_open_val
        )
        window_close_default = (
            convert_seconds_to_duration(window_close_val)
            if isinstance(window_close_val, int)
            else window_close_val
        )

        return vol.Schema({
            vol.Required(
                CONF_ROOM_NAME,
                default=room_data.get(CONF_ROOM_NAME) if room_data else None
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_TRV_ENTITIES,
                default=room_data.get(CONF_TRV_ENTITIES, []) if room_data else []
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="climate",
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_MAIN_TEMP_SENSOR,
                default=room_data.get(CONF_MAIN_TEMP_SENSOR) if room_data else None
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            ),
            vol.Optional(
                CONF_WINDOW_SENSORS,
                default=room_data.get(CONF_WINDOW_SENSORS, []) if room_data else []
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class=["window", "door", "opening"],
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_WEATHER_ENTITY,
                default=room_data.get(CONF_WEATHER_ENTITY) if room_data else None
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(
                CONF_OUTDOOR_SENSOR,
                default=room_data.get(CONF_OUTDOOR_SENSOR) if room_data else None
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            ),
            vol.Optional(
                CONF_WINDOW_OPEN_TIMEOUT,
                default=window_open_default,
                description={"suggested_value": window_open_default},
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            vol.Optional(
                CONF_WINDOW_CLOSE_TIMEOUT,
                default=window_close_default,
                description={"suggested_value": window_close_default},
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            vol.Optional(
                CONF_DONT_HEAT_BELOW_OUTDOOR,
                default=(
                    room_data.get(CONF_DONT_HEAT_BELOW_OUTDOOR, global_dont_heat)
                    if room_data
                    else global_dont_heat
                ),
                description={"suggested_value": global_dont_heat},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=35,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_USE_EARLY_START,
                default=(
                    room_data.get(CONF_USE_EARLY_START, global_early_start)
                    if room_data
                    else global_early_start
                ),
                description={"suggested_value": global_early_start},
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_LEARN_HEATING_RATE,
                default=(
                    room_data.get(CONF_LEARN_HEATING_RATE, global_learn)
                    if room_data
                    else global_learn
                ),
                description={"suggested_value": global_learn},
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_TARGET_TEMP_STEP,
                default=(
                    room_data.get(CONF_TARGET_TEMP_STEP, DEFAULT_TARGET_TEMP_STEP)
                    if room_data
                    else DEFAULT_TARGET_TEMP_STEP
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TEMP_STEP_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_TOLERANCE,
                default=(
                    room_data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)
                    if room_data
                    else DEFAULT_TOLERANCE
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TOLERANCE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
