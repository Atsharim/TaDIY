"""Config flow for TaDIY integration."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_EARLY_START_MAX,
    CONF_GLOBAL_EARLY_START_OFFSET,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_HUB,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
)
from .options_flow import TaDIYOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


class TaDIYConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaDIY."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TaDIYOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TaDIYOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Check if hub already exists
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        hub_exists = any(
            entry.data.get(CONF_HUB, False) for entry in existing_entries
        )

        if not hub_exists:
            # First setup: Create Hub automatically
            return await self.async_step_hub(user_input)
        else:
            # Subsequent setup: Add Room
            return await self.async_step_room(user_input)

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Hub setup - creates automatically with defaults."""
        try:
            # Set unique ID for hub
            await self.async_set_unique_id("{}_hub".format(DOMAIN))
            self._abort_if_unique_id_configured()

            # Create hub with default values
            hub_data = {
                "name": "TaDIY Hub",
                CONF_HUB: True,
                CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: DEFAULT_WINDOW_OPEN_TIMEOUT,
                CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: DEFAULT_WINDOW_CLOSE_TIMEOUT,
                CONF_GLOBAL_DONT_HEAT_BELOW: DEFAULT_DONT_HEAT_BELOW,
                CONF_GLOBAL_USE_EARLY_START: DEFAULT_USE_EARLY_START,
                CONF_GLOBAL_LEARN_HEATING_RATE: DEFAULT_LEARN_HEATING_RATE,
                CONF_GLOBAL_EARLY_START_OFFSET: DEFAULT_EARLY_START_OFFSET,
                CONF_GLOBAL_EARLY_START_MAX: DEFAULT_EARLY_START_MAX,
            }

            return self.async_create_entry(
                title="TaDIY Hub",
                data=hub_data,
            )
        except Exception:
            _LOGGER.exception("Unexpected exception during hub setup")
            return self.async_abort(reason="unknown")

    async def async_step_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Room setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                room_name = user_input[CONF_ROOM_NAME]

                # Find hub entry
                hub_entry = None
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data.get(CONF_HUB, False):
                        hub_entry = entry
                        break

                if not hub_entry:
                    return self.async_abort(reason="no_hub_found")

                # Check for duplicate room names
                existing_entries = self.hass.config_entries.async_entries(DOMAIN)
                existing_rooms = [
                    entry
                    for entry in existing_entries
                    if entry.data.get(CONF_ROOM_NAME) == room_name
                    and not entry.data.get(CONF_HUB, False)
                ]

                if existing_rooms:
                    errors["base"] = "room_already_exists"
                else:
                    # Generate unique_id based on timestamp (not room_name to allow renaming)
                    unique_id = "{}_room_{}".format(DOMAIN, int(time.time()))
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    # Add hub_entry_id to room data for via_device
                    user_input["hub_entry_id"] = hub_entry.entry_id

                    # Remove empty optional fields
                    cleaned_data = {k: v for k, v in user_input.items() if v not in ("", [], None)}

                    return self.async_create_entry(
                        title=room_name,
                        data=cleaned_data,
                    )
            except Exception:
                _LOGGER.exception("Unexpected exception during room setup")
                errors["base"] = "unknown"

        # Build schema step-by-step to avoid validation errors
        # Same fix as in options_flow.py - complex dict literals cause issues
        schema_dict = {
            vol.Required(CONF_ROOM_NAME): selector.TextSelector()
        }

        schema_dict[vol.Required(CONF_TRV_ENTITIES)] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="climate",
                multiple=True,
            )
        )

        schema_dict[vol.Optional(CONF_MAIN_TEMP_SENSOR, default="")] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        schema_dict[vol.Optional(CONF_WINDOW_SENSORS, default=[])] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="binary_sensor",
                multiple=True,
            )
        )

        schema_dict[vol.Optional(CONF_OUTDOOR_SENSOR, default="")] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
