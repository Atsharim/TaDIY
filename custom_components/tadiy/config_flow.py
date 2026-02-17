"""Config flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    DEFAULT_DONT_HEAT_BELOW,
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


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    return {"title": data[CONF_NAME]}


class TaDIYConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaDIY."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_NAME])
                self._abort_if_unique_id_configured()
                
                self._data = user_input
                return await self.async_step_global_defaults()
                
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
        )

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure global defaults for all rooms."""
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
                options={},
            )

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=vol.Schema({
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
            }),
            description_placeholders={
                "name": self._data[CONF_NAME],
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TaDIYOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TaDIYOptionsFlowHandler(config_entry)
