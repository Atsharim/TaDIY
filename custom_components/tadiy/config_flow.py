"""Config flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_NAME
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
    DEFAULT_NAME,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
)
from .options_flow import TaDIYOptionsFlowHandler

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


class TaDIYConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaDIY."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TaDIYOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TaDIYOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Check if hub already exists
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        hub_exists = any(entry.data.get(CONF_HUB, False) for entry in existing_entries)

        if not hub_exists:
            # First setup = Hub
            return await self.async_step_hub(user_input)
        else:
            # Subsequent = Room
            return await self.async_step_room(user_input)

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Hub setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.async_set_unique_id(f"{DOMAIN}_hub")
                self._abort_if_unique_id_configured()
                self._data = user_input
                self._data[CONF_HUB] = True
                return await self.async_step_global_defaults()
            except Exception:
                _LOGGER.exception("Unexpected exception during hub setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure global defaults."""
        if user_input is not None:
            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_OPEN_TIMEOUT), dict):
                user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT]
                )
            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT), dict):
                user_input[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT]
                )

            self._data.update(user_input)
            
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
            )

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                        default=convert_seconds_to_duration(DEFAULT_WINDOW_OPEN_TIMEOUT),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                        default=convert_seconds_to_duration(DEFAULT_WINDOW_CLOSE_TIMEOUT),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_GLOBAL_DONT_HEAT_BELOW,
                        default=DEFAULT_DONT_HEAT_BELOW,
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
                        default=DEFAULT_USE_EARLY_START,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_LEARN_HEATING_RATE,
                        default=DEFAULT_LEARN_HEATING_RATE,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_EARLY_START_OFFSET,
                        default=DEFAULT_EARLY_START_OFFSET,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=60,
                            step=5,
                            unit_of_measurement="min",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_GLOBAL_EARLY_START_MAX,
                        default=DEFAULT_EARLY_START_MAX,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=15,
                            max=240,
                            step=15,
                            unit_of_measurement="min",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                }
            ),
        )

    async def async_step_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Room setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                room_name = user_input[CONF_ROOM_NAME]

                # Check if room already exists
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
                    await self.async_set_unique_id(f"{DOMAIN}_room_{room_name}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=room_name,
                        data=user_input,
                    )
            except Exception:
                _LOGGER.exception("Unexpected exception during room setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROOM_NAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        )
                    ),
                    vol.Required(CONF_TRV_ENTITIES): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="climate",
                            multiple=True,
                        )
                    ),
                    vol.Optional(CONF_MAIN_TEMP_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                    vol.Optional(CONF_WINDOW_SENSORS): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor"],
                            multiple=True,
                        )
                    ),
                    vol.Optional(CONF_OUTDOOR_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                }
            ),
            errors=errors,
        )