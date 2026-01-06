"""Config flow for TaDIY."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TaDIYConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaDIY."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow one instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="TaDIY - Adaptive Climate Orchestrator",
                data={},
                options={"rooms": []},  # Empty room list initially
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "TaDIY will be set up. Rooms can be added after installation via 'Configure'."
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        from .options_flow import TaDIYOptionsFlowHandler
        return TaDIYOptionsFlowHandler(config_entry)
