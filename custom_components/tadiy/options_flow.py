"""Options flow for TaDIY."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_TRV_ENTITIES,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
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
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_room", "edit_room", "delete_room"],
            description_placeholders={
                "room_count": str(len(self.config_entry.options.get(CONF_ROOMS, []))),
            },
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        errors = {}

        if user_input is not None:
            # Validation
            room_name = user_input[CONF_ROOM_NAME].strip()
            existing_rooms = self.config_entry.options.get(CONF_ROOMS, [])
            
            if any(r[CONF_ROOM_NAME] == room_name for r in existing_rooms):
                errors["base"] = "room_exists"
            else:
                # Add room
                new_room = {
                    CONF_ROOM_NAME: room_name,
                    CONF_TRV_ENTITIES: user_input[CONF_TRV_ENTITIES],
                    CONF_MAIN_TEMP_SENSOR: user_input[CONF_MAIN_TEMP_SENSOR],
                    CONF_WINDOW_SENSORS: user_input.get(CONF_WINDOW_SENSORS, []),
                    CONF_WEATHER_ENTITY: user_input.get(CONF_WEATHER_ENTITY, ""),
                    CONF_OUTDOOR_SENSOR: user_input.get(CONF_OUTDOOR_SENSOR, ""),
                    CONF_WINDOW_OPEN_TIMEOUT: user_input[CONF_WINDOW_OPEN_TIMEOUT],
                    CONF_WINDOW_CLOSE_TIMEOUT: user_input[CONF_WINDOW_CLOSE_TIMEOUT],
                    CONF_DONT_HEAT_BELOW_OUTDOOR: user_input[CONF_DONT_HEAT_BELOW_OUTDOOR],
                }
                
                updated_rooms = existing_rooms + [new_room]
                
                return self.async_create_entry(
                    title="",
                    data={CONF_ROOMS: updated_rooms},
                )

        # Entity selectors
        data_schema = vol.Schema({
            vol.Required(CONF_ROOM_NAME): str,
            vol.Required(CONF_TRV_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="climate",
                    multiple=True,
                )
            ),
            vol.Required(CONF_MAIN_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            ),
            vol.Optional(CONF_WINDOW_SENSORS): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class="window",
                    multiple=True,
                )
            ),
            vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_OUTDOOR_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            ),
            vol.Optional(
                CONF_WINDOW_OPEN_TIMEOUT, 
                default=DEFAULT_WINDOW_OPEN_TIMEOUT
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=30,
                    max=3600,
                    step=30,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_WINDOW_CLOSE_TIMEOUT, 
                default=DEFAULT_WINDOW_CLOSE_TIMEOUT
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=60,
                    max=7200,
                    step=60,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_DONT_HEAT_BELOW_OUTDOOR, 
                default=DEFAULT_DONT_HEAT_BELOW
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=30,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        })

        return self.async_show_form(
            step_id="add_room",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Multiple TRVs/window sensors can be selected simultaneously."
            },
        )

    async def async_step_edit_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit existing room - select room first."""
        existing_rooms = self.config_entry.options.get(CONF_ROOMS, [])
        
        if not existing_rooms:
            return self.async_abort(reason="no_rooms")

        if user_input is not None:
            self._room_index = int(user_input["room_index"])
            self._current_room = existing_rooms[self._room_index]
            return await self.async_step_edit_room_config()

        
