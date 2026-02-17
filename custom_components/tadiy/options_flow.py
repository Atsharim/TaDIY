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
    DEFAULT_HUB_MODES,
    DOMAIN,
    MAX_CUSTOM_MODES,
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
            # Hub: Show init menu
            return await self.async_step_init_hub(user_input)

        # Room: Show basic configuration form
        return await self.async_step_room_config(user_input)

    async def async_step_init_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Hub initial configuration menu."""
        # Count rooms for display
        room_count = sum(
            1 for entry in self.hass.config_entries.async_entries(DOMAIN)
            if not entry.data.get(CONF_HUB, False)
        )

        # Hardcoded labels as workaround for translation caching issues
        return self.async_show_menu(
            step_id="init_hub",
            menu_options={
                "add_mode": "Add Custom Mode",
                "remove_mode": "Remove Custom Mode",
                "view_modes": "View All Modes",
            },
            description_placeholders={"room_count": str(room_count)},
        )

    async def async_step_add_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a custom mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mode_name = user_input.get("mode_name", "").strip().lower()

            # Get coordinator
            entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
            if not entry_data:
                return self.async_abort(reason="coordinator_not_found")

            coordinator = entry_data.get("coordinator")
            if not coordinator:
                return self.async_abort(reason="coordinator_not_found")

            # Try to add mode
            if not mode_name:
                errors["mode_name"] = "empty_name"
            elif mode_name in DEFAULT_HUB_MODES:
                errors["mode_name"] = "is_default_mode"
            elif mode_name in coordinator.get_custom_modes():
                errors["mode_name"] = "already_exists"
            elif len(coordinator.get_custom_modes()) >= MAX_CUSTOM_MODES:
                errors["mode_name"] = "mode_limit_reached"
            else:
                # Add the mode
                if coordinator.add_custom_mode(mode_name):
                    await coordinator.async_save_schedules()
                    return self.async_create_entry(title="", data={})
                else:
                    errors["base"] = "add_failed"

        return self.async_show_form(
            step_id="add_mode",
            data_schema=vol.Schema(
                {
                    vol.Required("mode_name"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a custom mode."""
        # Get coordinator
        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if not entry_data:
            return self.async_abort(reason="coordinator_not_found")

        coordinator = entry_data.get("coordinator")
        if not coordinator:
            return self.async_abort(reason="coordinator_not_found")

        # Get custom modes (exclude defaults)
        all_modes = coordinator.get_custom_modes()
        custom_only = [m for m in all_modes if m not in DEFAULT_HUB_MODES]

        if not custom_only:
            return self.async_abort(reason="no_custom_modes")

        if user_input is not None:
            mode_to_remove = user_input.get("mode_to_remove")
            if mode_to_remove:
                coordinator.remove_custom_mode(mode_to_remove)
                await coordinator.async_save_schedules()
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="remove_mode",
            data_schema=vol.Schema(
                {
                    vol.Required("mode_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=custom_only,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_view_modes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """View all modes."""
        # Get coordinator
        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if not entry_data:
            return self.async_abort(reason="coordinator_not_found")

        coordinator = entry_data.get("coordinator")
        if not coordinator:
            return self.async_abort(reason="coordinator_not_found")

        all_modes = coordinator.get_custom_modes()
        default_modes = [m for m in all_modes if m in DEFAULT_HUB_MODES]
        custom_modes = [m for m in all_modes if m not in DEFAULT_HUB_MODES]

        description = "**Default Modes (cannot be removed):**\n"
        description += ", ".join(default_modes) + "\n\n"
        description += f"**Custom Modes ({len(custom_modes)}/{MAX_CUSTOM_MODES - len(DEFAULT_HUB_MODES)}):**\n"
        if custom_modes:
            description += ", ".join(custom_modes)
        else:
            description += "None"

        return self.async_show_form(
            step_id="view_modes",
            data_schema=vol.Schema({}),
            description_placeholders={"modes_info": description},
        )

    async def async_step_room_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room basic settings."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)

            # Remove empty optional fields instead of storing "" or []
            for key, value in user_input.items():
                if value in ("", [], None):
                    new_data.pop(key, None)
                else:
                    new_data[key] = value

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data

        # Build schema step-by-step to avoid 400 Bad Request
        # CRITICAL: Complex dict literals with TextSelectorConfig cause validation errors
        # Solution: Start with simple dict, then add fields one by one
        schema_dict = {
            vol.Required(
                CONF_ROOM_NAME,
                default=current_data.get(CONF_ROOM_NAME, ""),
            ): selector.TextSelector()  # Simplified - no config needed
        }

        # Add TRV entities (required field)
        schema_dict[vol.Required(
            CONF_TRV_ENTITIES,
            default=current_data.get(CONF_TRV_ENTITIES, []),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="climate",
                multiple=True,
            )
        )

        # Add optional fields with explicit defaults
        schema_dict[vol.Optional(
            CONF_MAIN_TEMP_SENSOR,
            default=current_data.get(CONF_MAIN_TEMP_SENSOR, ""),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        schema_dict[vol.Optional(
            CONF_WINDOW_SENSORS,
            default=current_data.get(CONF_WINDOW_SENSORS, []),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="binary_sensor",
                multiple=True,
            )
        )

        schema_dict[vol.Optional(
            CONF_OUTDOOR_SENSOR,
            default=current_data.get(CONF_OUTDOOR_SENSOR, ""),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        return self.async_show_form(
            step_id="room_config",
            data_schema=vol.Schema(schema_dict),
        )
