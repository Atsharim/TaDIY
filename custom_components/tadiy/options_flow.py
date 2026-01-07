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
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_TARGET_TEMP_STEP,
    CONF_TOLERANCE,
    CONF_TRV_ENTITIES,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    TEMP_STEP_OPTIONS,
    TOLERANCE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


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
            menu_options=["add_room", "edit_room_select", "delete_room_select"],
            description_placeholders={
                "room_count": str(room_count),
            },
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate room name is unique
            existing_rooms = self.config_entry.options.get(CONF_ROOMS, [])
            room_names = [r.get(CONF_ROOM_NAME) for r in existing_rooms]
            
            if user_input[CONF_ROOM_NAME] in room_names:
                errors["room_name"] = "Room name already exists"
            else:
                # Convert duration to seconds if needed
                if isinstance(user_input.get(CONF_WINDOW_OPEN_TIMEOUT), dict):
                    user_input[CONF_WINDOW_OPEN_TIMEOUT] = (
                        user_input[CONF_WINDOW_OPEN_TIMEOUT].get("hours", 0) * 3600 +
                        user_input[CONF_WINDOW_OPEN_TIMEOUT].get("minutes", 0) * 60 +
                        user_input[CONF_WINDOW_OPEN_TIMEOUT].get("seconds", 0)
                    )
                
                if isinstance(user_input.get(CONF_WINDOW_CLOSE_TIMEOUT), dict):
                    user_input[CONF_WINDOW_CLOSE_TIMEOUT] = (
                        user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("hours", 0) * 3600 +
                        user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("minutes", 0) * 60 +
                        user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("seconds", 0)
                    )
                
                # Add the new room
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
                    selector.SelectSelectorConfig(options=room_names)
                ),
            }),
        )

    async def async_step_edit_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing room."""
        if user_input is not None:
            # Convert duration to seconds if needed
            if isinstance(user_input.get(CONF_WINDOW_OPEN_TIMEOUT), dict):
                user_input[CONF_WINDOW_OPEN_TIMEOUT] = (
                    user_input[CONF_WINDOW_OPEN_TIMEOUT].get("hours", 0) * 3600 +
                    user_input[CONF_WINDOW_OPEN_TIMEOUT].get("minutes", 0) * 60 +
                    user_input[CONF_WINDOW_OPEN_TIMEOUT].get("seconds", 0)
                )
            
            if isinstance(user_input.get(CONF_WINDOW_CLOSE_TIMEOUT), dict):
                user_input[CONF_WINDOW_CLOSE_TIMEOUT] = (
                    user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("hours", 0) * 3600 +
                    user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("minutes", 0) * 60 +
                    user_input[CONF_WINDOW_CLOSE_TIMEOUT].get("seconds", 0)
                )
            
            # Update the room
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
            new_rooms = [
                r for r in rooms if r.get(CONF_ROOM_NAME) != room_name
            ]
            
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_ROOMS: new_rooms}
            )

        room_names = [r.get(CONF_ROOM_NAME, f"Room {i}") for i, r in enumerate(rooms)]
        
        return self.async_show_form(
            step_id="delete_room_select",
            data_schema=vol.Schema({
                vol.Required("room"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=room_names)
                ),
            }),
        )

    def _room_schema(self, room_data: dict[str, Any] | None = None) -> vol.Schema:
        """Generate room configuration schema."""
        # Convert seconds back to duration dict for display
        window_open_default = room_data.get(CONF_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT) if room_data else DEFAULT_WINDOW_OPEN_TIMEOUT
        window_close_default = room_data.get(CONF_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT) if room_data else DEFAULT_WINDOW_CLOSE_TIMEOUT
        
        if isinstance(window_open_default, int):
            window_open_default = {
                "hours": window_open_default // 3600,
                "minutes": (window_open_default % 3600) // 60,
                "seconds": window_open_default % 60,
            }
        
        if isinstance(window_close_default, int):
            window_close_default = {
                "hours": window_close_default // 3600,
                "minutes": (window_close_default % 3600) // 60,
                "seconds": window_close_default % 60,
            }
        
        return vol.Schema({
            vol.Required(
                CONF_ROOM_NAME,
                default=room_data.get(CONF_ROOM_NAME) if room_data else None
            ): selector.TextSelector(),
            
            vol.Required(
                CONF_TRV_ENTITIES,
                default=room_data.get(CONF_TRV_ENTITIES, []) if room_data else []
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="climate",
                    multiple=True
                )
            ),
            
            vol.Required(
                CONF_MAIN_TEMP_SENSOR,
                default=room_data.get(CONF_MAIN_TEMP_SENSOR) if room_data else None
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature"
                )
            ),
            
            vol.Optional(
                CONF_WINDOW_SENSORS,
                default=room_data.get(CONF_WINDOW_SENSORS, []) if room_data else []
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class=["window", "door", "opening"],
                    multiple=True
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
                    device_class="temperature"
                )
            ),
            
            vol.Optional(
                CONF_WINDOW_OPEN_TIMEOUT,
                default=window_open_default
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            
            vol.Optional(
                CONF_WINDOW_CLOSE_TIMEOUT,
                default=window_close_default
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=False)
            ),
            
            vol.Optional(
                CONF_DONT_HEAT_BELOW_OUTDOOR,
                default=room_data.get(CONF_DONT_HEAT_BELOW_OUTDOOR, DEFAULT_DONT_HEAT_BELOW) if room_data else DEFAULT_DONT_HEAT_BELOW
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-10,
                    max=35,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode="slider"
                )
            ),
            
            vol.Optional(
                CONF_TARGET_TEMP_STEP,
                default=room_data.get(CONF_TARGET_TEMP_STEP, DEFAULT_TARGET_TEMP_STEP) if room_data else DEFAULT_TARGET_TEMP_STEP
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TEMP_STEP_OPTIONS,
                    mode="dropdown"
                )
            ),
            
            vol.Optional(
                CONF_TOLERANCE,
                default=room_data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE) if room_data else DEFAULT_TOLERANCE
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TOLERANCE_OPTIONS,
                    mode="dropdown"
                )
            ),
        })
