"""Options flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
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
    DEFAULT_HUB_MODES,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
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

        return self.async_show_menu(
            step_id="init_hub",
            menu_options=["global_defaults", "hub_mode"],
            description_placeholders={"room_count": str(room_count)},
        )

    async def async_step_hub_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Hub options menu for custom modes."""
        return self.async_show_menu(
            step_id="hub_menu",
            menu_options=["add_mode", "remove_mode", "view_modes"],
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

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure global default settings."""
        if user_input is not None:
            # Update hub config entry
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            # Reload the entry to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                        default=current_data.get(CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=3600,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                        default=current_data.get(CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=3600,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_GLOBAL_DONT_HEAT_BELOW,
                        default=current_data.get(CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5.0,
                            max=30.0,
                            step=0.5,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_GLOBAL_USE_EARLY_START,
                        default=current_data.get(CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_LEARN_HEATING_RATE,
                        default=current_data.get(CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_EARLY_START_OFFSET,
                        default=current_data.get(CONF_GLOBAL_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=60,
                            unit_of_measurement="minutes",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_GLOBAL_EARLY_START_MAX,
                        default=current_data.get(CONF_GLOBAL_EARLY_START_MAX, DEFAULT_EARLY_START_MAX),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=240,
                            unit_of_measurement="minutes",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_hub_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change hub mode."""
        # Get coordinator
        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if not entry_data:
            return self.async_abort(reason="coordinator_not_found")

        coordinator = entry_data.get("coordinator")
        if not coordinator:
            return self.async_abort(reason="coordinator_not_found")

        if user_input is not None:
            mode = user_input.get("hub_mode")
            if mode:
                coordinator.set_hub_mode(mode)
                await coordinator.async_save_schedules()
                await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data={})

        # Get available modes from coordinator
        available_modes = coordinator.get_custom_modes()

        return self.async_show_form(
            step_id="hub_mode",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "hub_mode",
                        default=coordinator.get_hub_mode(),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=available_modes,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_room_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room basic settings."""
        if user_input is not None:
            # We need to update data in config entry, but properly
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            # Reload the entry to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

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
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete=None,
                        )
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
