"""Options flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_HUB,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_WINDOW_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


class TaDIYOptionsFlowHandler(OptionsFlow):
    """Handle options flow for TaDIY."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    @property
    def config_entry(self) -> ConfigEntry:
        """Return config entry."""
        return self._entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        is_hub = self.config_entry.data.get(CONF_HUB, False)

        if is_hub:
            # Hub: No configuration via options (managed via entities)
            return self.async_abort(reason="hub_not_configurable")

        # Room: Show basic configuration form
        return await self.async_step_room_config(user_input)

    async def async_step_room_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room basic settings."""
        if user_input is not None:
            # Update entry data (not options)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data

        # Show ONLY basic config fields
        return self.async_show_form(
            step_id="room_config",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ROOM_NAME,
                        default=current_data.get(CONF_ROOM_NAME, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Required(
                        CONF_TRV_ENTITIES,
                        default=current_data.get(CONF_TRV_ENTITIES, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="climate",
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CONF_MAIN_TEMP_SENSOR,
                        default=current_data.get(CONF_MAIN_TEMP_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                    vol.Optional(
                        CONF_WINDOW_SENSORS,
                        default=current_data.get(CONF_WINDOW_SENSORS, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="binary_sensor",
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CONF_OUTDOOR_SENSOR,
                        default=current_data.get(CONF_OUTDOOR_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                        )
                    ),
                }
            ),
        )
