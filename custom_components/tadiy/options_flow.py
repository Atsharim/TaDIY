"""Options flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_EARLY_START_MAX,
    CONF_EARLY_START_OFFSET,
    CONF_GLOBAL_OVERRIDE_TIMEOUT,
    CONF_HUB,
    CONF_HUMIDITY_SENSOR,
    CONF_HYSTERESIS,
    CONF_LOCATION_MODE_ENABLED,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_OVERRIDE_TIMEOUT,
    CONF_PERSON_ENTITIES,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_ROOM_NAME,
    CONF_SHOW_PANEL,
    CONF_TRV_ENTITIES,
    CONF_USE_PID_CONTROL,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_GLOBAL_OVERRIDE_TIMEOUT,
    DEFAULT_HUB_MODES,
    DEFAULT_HYSTERESIS,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_USE_PID_CONTROL,
    DOMAIN,
    MAX_CUSTOM_MODES,
    MAX_HYSTERESIS,
    MIN_HYSTERESIS,
    OVERRIDE_TIMEOUT_1H,
    OVERRIDE_TIMEOUT_2H,
    OVERRIDE_TIMEOUT_3H,
    OVERRIDE_TIMEOUT_4H,
    OVERRIDE_TIMEOUT_ALWAYS,
    OVERRIDE_TIMEOUT_NEVER,
    OVERRIDE_TIMEOUT_NEXT_BLOCK,
    OVERRIDE_TIMEOUT_NEXT_DAY,
)
from .schedule_editor_flow import ScheduleEditorMixin

_LOGGER = logging.getLogger(__name__)


class TaDIYOptionsFlowHandler(ScheduleEditorMixin, OptionsFlow):
    """Handle options flow for TaDIY."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry
        # Schedule editor state
        self._selected_mode: str | None = None
        self._selected_schedule_type: str | None = None
        self._editing_blocks: list[dict[str, Any]] = []
        self._use_normal_default: bool = False

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

        # Room: Show menu with config and schedule options
        return await self.async_step_init_room(user_input)

    async def async_step_init_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Room initial menu - directly show room config."""
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
                "panel_settings": "Panel Settings",
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

    async def async_step_panel_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure panel visibility and hub-level entities."""
        if user_input is not None:
            # Update config entry with new settings
            new_data = dict(self.config_entry.data)
            new_data[CONF_SHOW_PANEL] = user_input.get(CONF_SHOW_PANEL, True)

            # Remove empty optional fields
            for key in [CONF_WEATHER_ENTITY, CONF_PERSON_ENTITIES]:
                value = user_input.get(key)
                if value in ("", [], None):
                    new_data.pop(key, None)
                else:
                    new_data[key] = value

            # Location mode enabled
            new_data[CONF_LOCATION_MODE_ENABLED] = user_input.get(CONF_LOCATION_MODE_ENABLED, False)

            # Override timeout (Hub setting)
            override_timeout = user_input.get(CONF_GLOBAL_OVERRIDE_TIMEOUT)
            if override_timeout:
                new_data[CONF_GLOBAL_OVERRIDE_TIMEOUT] = override_timeout
            else:
                new_data.pop(CONF_GLOBAL_OVERRIDE_TIMEOUT, None)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Trigger panel update by reloading entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Get current settings
        current_data = self.config_entry.data
        current_show_panel = current_data.get(CONF_SHOW_PANEL, True)
        current_weather = current_data.get(CONF_WEATHER_ENTITY, "")
        current_persons = current_data.get(CONF_PERSON_ENTITIES, [])
        current_location_mode = current_data.get(CONF_LOCATION_MODE_ENABLED, False)
        current_override_timeout = current_data.get(CONF_GLOBAL_OVERRIDE_TIMEOUT, DEFAULT_GLOBAL_OVERRIDE_TIMEOUT)

        # Build schema step-by-step
        schema_dict = {
            vol.Required(CONF_SHOW_PANEL, default=current_show_panel): bool
        }

        schema_dict[vol.Optional(
            CONF_WEATHER_ENTITY,
            default=current_weather,
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="weather",
            )
        )

        schema_dict[vol.Optional(
            CONF_PERSON_ENTITIES,
            default=current_persons,
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="person",
                multiple=True,
            )
        )

        schema_dict[vol.Required(
            CONF_LOCATION_MODE_ENABLED,
            default=current_location_mode,
        )] = bool

        schema_dict[vol.Optional(
            CONF_GLOBAL_OVERRIDE_TIMEOUT,
            default=current_override_timeout,
        )] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEVER, label="Never (manual changes stay forever)"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_1H, label="1 hour"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_2H, label="2 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_3H, label="3 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_4H, label="4 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEXT_BLOCK, label="Until next schedule block (Recommended)"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEXT_DAY, label="Until next day (midnight)"),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        return self.async_show_form(
            step_id="panel_settings",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": (
                    "Hub Configuration:\n\n"
                    "• Panel: Show TaDIY Schedules in sidebar\n"
                    "• Weather Entity: Optional weather entity for outdoor temperature fallback and future forecast support\n"
                    "• Person Entities: Optional person tracking for location-based heating control\n"
                    "• Location Mode: Enable automatic heating reduction when nobody is home\n"
                    "• Override Timeout: How long manual TRV changes override schedules (applies to all rooms by default)"
                )
            },
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

            # Save feature settings if hysteresis or PID changed
            if CONF_HYSTERESIS in user_input or CONF_USE_PID_CONTROL in user_input:
                coordinator = self.hass.data[DOMAIN].get(self.config_entry.entry_id, {}).get("coordinator")
                if coordinator and hasattr(coordinator, "async_save_feature_settings"):
                    # Update hysteresis in controller
                    if CONF_HYSTERESIS in user_input:
                        coordinator.heating_controller.set_hysteresis(user_input[CONF_HYSTERESIS])

                    # Update PID settings if changed
                    if CONF_USE_PID_CONTROL in user_input:
                        from .core.control import PIDConfig, PIDHeatingController, HeatingController

                        use_pid = user_input[CONF_USE_PID_CONTROL]
                        current_is_pid = isinstance(coordinator.heating_controller, PIDHeatingController)

                        if use_pid and not current_is_pid:
                            # Switch to PID controller
                            pid_config = PIDConfig(
                                kp=user_input.get(CONF_PID_KP, DEFAULT_PID_KP),
                                ki=user_input.get(CONF_PID_KI, DEFAULT_PID_KI),
                                kd=user_input.get(CONF_PID_KD, DEFAULT_PID_KD),
                            )
                            coordinator.heating_controller = PIDHeatingController(pid_config)
                            coordinator.heating_controller.set_hysteresis(user_input.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS))
                        elif not use_pid and current_is_pid:
                            # Switch to basic controller
                            hysteresis = coordinator.heating_controller.hysteresis
                            coordinator.heating_controller = HeatingController(hysteresis=hysteresis)
                        elif use_pid and current_is_pid:
                            # Update PID parameters
                            coordinator.heating_controller.config.kp = user_input.get(CONF_PID_KP, DEFAULT_PID_KP)
                            coordinator.heating_controller.config.ki = user_input.get(CONF_PID_KI, DEFAULT_PID_KI)
                            coordinator.heating_controller.config.kd = user_input.get(CONF_PID_KD, DEFAULT_PID_KD)

                    # Save to storage
                    await coordinator.async_save_feature_settings()

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
            CONF_HUMIDITY_SENSOR,
            default=current_data.get(CONF_HUMIDITY_SENSOR, ""),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="humidity",
            )
        )

        schema_dict[vol.Optional(
            CONF_WINDOW_SENSORS,
            default=current_data.get(CONF_WINDOW_SENSORS, []),
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="binary_sensor",
                device_class=["door", "window", "opening"],
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

        # Early Start Room Overrides (None = use hub setting)
        schema_dict[vol.Optional(
            CONF_EARLY_START_OFFSET,
            description={
                "suggested_value": current_data.get(CONF_EARLY_START_OFFSET)
            },
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=60,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        schema_dict[vol.Optional(
            CONF_EARLY_START_MAX,
            description={
                "suggested_value": current_data.get(CONF_EARLY_START_MAX)
            },
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=360,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # Override Timeout (Room level, includes "always" option)
        current_override_timeout = current_data.get(CONF_OVERRIDE_TIMEOUT, "")
        schema_dict[vol.Optional(
            CONF_OVERRIDE_TIMEOUT,
            default=current_override_timeout,
        )] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="", label="Use hub setting"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEVER, label="Never (manual changes stay forever)"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_1H, label="1 hour"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_2H, label="2 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_3H, label="3 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_4H, label="4 hours"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEXT_BLOCK, label="Until next schedule block"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_NEXT_DAY, label="Until next day (midnight)"),
                    selector.SelectOptionDict(value=OVERRIDE_TIMEOUT_ALWAYS, label="Always use schedule (no manual override)"),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        # Hysteresis
        current_hysteresis = current_data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        schema_dict[vol.Optional(
            CONF_HYSTERESIS,
            default=current_hysteresis,
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_HYSTERESIS,
                max=MAX_HYSTERESIS,
                step=0.1,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # PID Control
        current_use_pid = current_data.get(CONF_USE_PID_CONTROL, DEFAULT_USE_PID_CONTROL)
        schema_dict[vol.Optional(
            CONF_USE_PID_CONTROL,
            default=current_use_pid,
        )] = selector.BooleanSelector()

        # PID Parameters (only shown if PID is enabled, but always available in schema)
        current_pid_kp = current_data.get(CONF_PID_KP, DEFAULT_PID_KP)
        schema_dict[vol.Optional(
            CONF_PID_KP,
            default=current_pid_kp,
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1,
                max=5.0,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        current_pid_ki = current_data.get(CONF_PID_KI, DEFAULT_PID_KI)
        schema_dict[vol.Optional(
            CONF_PID_KI,
            default=current_pid_ki,
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.001,
                max=0.1,
                step=0.001,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        current_pid_kd = current_data.get(CONF_PID_KD, DEFAULT_PID_KD)
        schema_dict[vol.Optional(
            CONF_PID_KD,
            default=current_pid_kd,
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=1.0,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        return self.async_show_form(
            step_id="room_config",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": (
                    "Room Configuration:\n\n"
                    "• Early Start Offset: Additional minutes to start early (leave empty to use hub setting)\n"
                    "• Early Start Max: Maximum early start time in minutes (leave empty to use hub setting)\n"
                    "• Override Timeout: How long manual TRV changes override schedules (leave empty to use hub setting)\n"
                    "• Hysteresis: Temperature deadband to prevent rapid cycling (°C)\n"
                    "• PID Control: Enable advanced PID controller for smoother temperature regulation (opt-in)\n"
                    "• PID Kp: Proportional gain (higher = more aggressive response to temperature error)\n"
                    "• PID Ki: Integral gain (compensates for persistent error over time)\n"
                    "• PID Kd: Derivative gain (dampens oscillations, predicts future error)\n\n"
                    f"Hub Defaults: Offset={DEFAULT_EARLY_START_OFFSET}min, Max={DEFAULT_EARLY_START_MAX}min, Timeout={DEFAULT_GLOBAL_OVERRIDE_TIMEOUT}, Hysteresis={DEFAULT_HYSTERESIS}°C"
                )
            },
        )
