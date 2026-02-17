"""Options flow for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ADJACENT_ROOMS,
    CONF_AWAY_TEMPERATURE,
    CONF_COUPLING_STRENGTH,
    CONF_EARLY_START_MAX,
    CONF_EARLY_START_OFFSET,
    CONF_GLOBAL_OVERRIDE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_HEATING_CURVE_SLOPE,
    CONF_HUB,
    CONF_HUMIDITY_SENSOR,
    CONF_HYSTERESIS,
    CONF_DEBUG_ROOMS,
    CONF_DEBUG_HUB,
    CONF_DEBUG_PANEL,
    CONF_DEBUG_UI,
    CONF_DEBUG_CARDS,
    CONF_DEBUG_TRV,
    CONF_DEBUG_SENSORS,
    CONF_DEBUG_SCHEDULE,
    CONF_DEBUG_HEATING,
    CONF_DEBUG_CALIBRATION,
    CONF_DEBUG_EARLY_START,
    CONF_DEBUG_VERBOSE,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    CONF_SHOW_PANEL,
    CONF_PERSON_ENTITIES,
    CONF_LOCATION_MODE_ENABLED,
    CONF_USE_HEATING_CURVE,
    CONF_USE_WEATHER_PREDICTION,
    CONF_USE_PID_CONTROL,
    CONF_PID_KP,
    CONF_PID_KI,
    CONF_PID_KD,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_OVERRIDE_TIMEOUT,
    CONF_USE_HVAC_OFF_FOR_LOW_TEMP,
    CONF_USE_ROOM_COUPLING,
    DEFAULT_AWAY_TEMPERATURE,
    DEFAULT_COUPLING_STRENGTH,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_GLOBAL_OVERRIDE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_HEATING_CURVE_SLOPE,
    DEFAULT_HUB_MODES,
    DEFAULT_HYSTERESIS,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_USE_HEATING_CURVE,
    DEFAULT_USE_HVAC_OFF_FOR_LOW_TEMP,
    DEFAULT_USE_PID_CONTROL,
    DEFAULT_USE_ROOM_COUPLING,
    DEFAULT_USE_WEATHER_PREDICTION,
    DOMAIN,
    MAX_CUSTOM_MODES,
    MAX_HEATING_CURVE_SLOPE,
    MAX_HYSTERESIS,
    MIN_HEATING_CURVE_SLOPE,
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
            1
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if not entry.data.get(CONF_HUB, False)
        )

        # Hardcoded labels as workaround for translation caching issues
        return self.async_show_menu(
            step_id="init_hub",
            menu_options={
                "add_mode": "Add Custom Mode",
                "remove_mode": "Remove Custom Mode",
                "view_modes": "View All Modes",
                "panel_settings": "Hub Configuration",
                "debug_settings": "Debug Settings",
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
        if user_input is not None:
            return await self.async_step_init_hub()

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
        """Configure hub-level settings including panel, weather, early start, and heating curve."""
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
            new_data[CONF_LOCATION_MODE_ENABLED] = user_input.get(
                CONF_LOCATION_MODE_ENABLED, False
            )

            # Override timeout (Hub setting)
            override_timeout = user_input.get(CONF_GLOBAL_OVERRIDE_TIMEOUT)
            if override_timeout:
                new_data[CONF_GLOBAL_OVERRIDE_TIMEOUT] = override_timeout
            else:
                new_data.pop(CONF_GLOBAL_OVERRIDE_TIMEOUT, None)

            # Early Start settings (Hub-level)
            early_start_offset = user_input.get(CONF_EARLY_START_OFFSET)
            if early_start_offset is not None:
                new_data[CONF_EARLY_START_OFFSET] = early_start_offset
            early_start_max = user_input.get(CONF_EARLY_START_MAX)
            if early_start_max is not None:
                new_data[CONF_EARLY_START_MAX] = early_start_max

            # Window timeout settings (Hub-level)
            window_open_timeout = user_input.get(CONF_GLOBAL_WINDOW_OPEN_TIMEOUT)
            if window_open_timeout is not None:
                new_data[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT] = int(window_open_timeout)
            window_close_timeout = user_input.get(CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT)
            if window_close_timeout is not None:
                new_data[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT] = int(window_close_timeout)

            # Weather Compensation / Heating Curve settings (Hub-level)
            new_data[CONF_USE_HEATING_CURVE] = user_input.get(
                CONF_USE_HEATING_CURVE, DEFAULT_USE_HEATING_CURVE
            )
            heating_curve_slope = user_input.get(CONF_HEATING_CURVE_SLOPE)
            if heating_curve_slope is not None:
                new_data[CONF_HEATING_CURVE_SLOPE] = heating_curve_slope

            # Weather Prediction (Hub-level)
            new_data[CONF_USE_WEATHER_PREDICTION] = user_input.get(
                CONF_USE_WEATHER_PREDICTION, DEFAULT_USE_WEATHER_PREDICTION
            )

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
        current_override_timeout = current_data.get(
            CONF_GLOBAL_OVERRIDE_TIMEOUT, DEFAULT_GLOBAL_OVERRIDE_TIMEOUT
        )
        current_early_start_offset = current_data.get(
            CONF_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET
        )
        current_early_start_max = current_data.get(
            CONF_EARLY_START_MAX, DEFAULT_EARLY_START_MAX
        )
        current_use_heating_curve = current_data.get(
            CONF_USE_HEATING_CURVE, DEFAULT_USE_HEATING_CURVE
        )
        current_heating_curve_slope = current_data.get(
            CONF_HEATING_CURVE_SLOPE, DEFAULT_HEATING_CURVE_SLOPE
        )
        current_use_weather_prediction = current_data.get(
            CONF_USE_WEATHER_PREDICTION, DEFAULT_USE_WEATHER_PREDICTION
        )
        current_window_open_timeout = current_data.get(
            CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
        )
        current_window_close_timeout = current_data.get(
            CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
        )

        # Build schema step-by-step
        schema_dict = {vol.Required(CONF_SHOW_PANEL, default=current_show_panel): bool}

        schema_dict[
            vol.Optional(
                CONF_WEATHER_ENTITY,
                default=current_weather,
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="weather",
            )
        )

        schema_dict[
            vol.Optional(
                CONF_PERSON_ENTITIES,
                default=current_persons,
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="person",
                multiple=True,
            )
        )

        schema_dict[
            vol.Required(
                CONF_LOCATION_MODE_ENABLED,
                default=current_location_mode,
            )
        ] = bool

        schema_dict[
            vol.Optional(
                CONF_GLOBAL_OVERRIDE_TIMEOUT,
                default=current_override_timeout,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEVER,
                        label="Never (manual changes stay forever)",
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_1H, label="1 hour"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_2H, label="2 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_3H, label="3 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_4H, label="4 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEXT_BLOCK,
                        label="Until next schedule block (Recommended)",
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEXT_DAY,
                        label="Until next day (midnight)",
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        # Early Start settings
        schema_dict[
            vol.Optional(
                CONF_EARLY_START_OFFSET,
                default=current_early_start_offset,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=60,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        schema_dict[
            vol.Optional(
                CONF_EARLY_START_MAX,
                default=current_early_start_max,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=360,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # Window timeout settings
        schema_dict[
            vol.Optional(
                CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                default=current_window_open_timeout,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=1800,
                step=30,
                unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        schema_dict[
            vol.Optional(
                CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                default=current_window_close_timeout,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=600,
                step=30,
                unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # Weather Compensation / Heating Curve
        schema_dict[
            vol.Optional(
                CONF_USE_HEATING_CURVE,
                default=current_use_heating_curve,
            )
        ] = selector.BooleanSelector()

        schema_dict[
            vol.Optional(
                CONF_HEATING_CURVE_SLOPE,
                default=current_heating_curve_slope,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_HEATING_CURVE_SLOPE,
                max=MAX_HEATING_CURVE_SLOPE,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # Weather Prediction
        schema_dict[
            vol.Optional(
                CONF_USE_WEATHER_PREDICTION,
                default=current_use_weather_prediction,
            )
        ] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="panel_settings",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_debug_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure debug logging settings."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)

            # Master toggle - if disabled, disable all categories
            debug_enabled = user_input.get("debug_enabled", False)

            if debug_enabled:
                # Get selected categories from multi-select
                selected_categories = user_input.get("debug_categories", [])
                new_data[CONF_DEBUG_ROOMS] = "rooms" in selected_categories
                new_data[CONF_DEBUG_HUB] = "hub" in selected_categories
                new_data[CONF_DEBUG_PANEL] = "panel" in selected_categories
                new_data[CONF_DEBUG_UI] = "ui" in selected_categories
                new_data[CONF_DEBUG_CARDS] = "cards" in selected_categories
                new_data[CONF_DEBUG_TRV] = "trv" in selected_categories
                new_data[CONF_DEBUG_SENSORS] = "sensors" in selected_categories
                new_data[CONF_DEBUG_SCHEDULE] = "schedule" in selected_categories
                new_data[CONF_DEBUG_HEATING] = "heating" in selected_categories
                new_data[CONF_DEBUG_CALIBRATION] = "calibration" in selected_categories
                new_data[CONF_DEBUG_EARLY_START] = "early_start" in selected_categories
                new_data[CONF_DEBUG_VERBOSE] = "verbose" in selected_categories
            else:
                # Disable all
                new_data[CONF_DEBUG_ROOMS] = False
                new_data[CONF_DEBUG_HUB] = False
                new_data[CONF_DEBUG_PANEL] = False
                new_data[CONF_DEBUG_UI] = False
                new_data[CONF_DEBUG_CARDS] = False
                new_data[CONF_DEBUG_TRV] = False
                new_data[CONF_DEBUG_SENSORS] = False
                new_data[CONF_DEBUG_SCHEDULE] = False
                new_data[CONF_DEBUG_HEATING] = False
                new_data[CONF_DEBUG_CALIBRATION] = False
                new_data[CONF_DEBUG_EARLY_START] = False
                new_data[CONF_DEBUG_VERBOSE] = False

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Trigger reload for changes to take effect
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Get current settings
        current_data = self.config_entry.data

        # Check if any debug is enabled
        any_debug_enabled = (
            current_data.get(CONF_DEBUG_ROOMS, False)
            or current_data.get(CONF_DEBUG_HUB, False)
            or current_data.get(CONF_DEBUG_PANEL, False)
            or current_data.get(CONF_DEBUG_UI, False)
            or current_data.get(CONF_DEBUG_CARDS, False)
            or current_data.get(CONF_DEBUG_TRV, False)
            or current_data.get(CONF_DEBUG_SENSORS, False)
            or current_data.get(CONF_DEBUG_SCHEDULE, False)
            or current_data.get(CONF_DEBUG_HEATING, False)
            or current_data.get(CONF_DEBUG_CALIBRATION, False)
            or current_data.get(CONF_DEBUG_EARLY_START, False)
            or current_data.get(CONF_DEBUG_VERBOSE, False)
        )

        # Build list of currently enabled categories
        enabled_categories = []
        if current_data.get(CONF_DEBUG_ROOMS, False):
            enabled_categories.append("rooms")
        if current_data.get(CONF_DEBUG_HUB, False):
            enabled_categories.append("hub")
        if current_data.get(CONF_DEBUG_PANEL, False):
            enabled_categories.append("panel")
        if current_data.get(CONF_DEBUG_UI, False):
            enabled_categories.append("ui")
        if current_data.get(CONF_DEBUG_CARDS, False):
            enabled_categories.append("cards")
        if current_data.get(CONF_DEBUG_TRV, False):
            enabled_categories.append("trv")
        if current_data.get(CONF_DEBUG_SENSORS, False):
            enabled_categories.append("sensors")
        if current_data.get(CONF_DEBUG_SCHEDULE, False):
            enabled_categories.append("schedule")
        if current_data.get(CONF_DEBUG_HEATING, False):
            enabled_categories.append("heating")
        if current_data.get(CONF_DEBUG_CALIBRATION, False):
            enabled_categories.append("calibration")
        if current_data.get(CONF_DEBUG_EARLY_START, False):
            enabled_categories.append("early_start")
        if current_data.get(CONF_DEBUG_VERBOSE, False):
            enabled_categories.append("verbose")

        schema_dict = {
            vol.Required("debug_enabled", default=any_debug_enabled): bool,
        }

        schema_dict[vol.Optional("debug_categories", default=enabled_categories)] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value="trv",
                            label="TRV Commands (temperatures sent to TRVs, calibration)",
                        ),
                        selector.SelectOptionDict(
                            value="sensors",
                            label="Sensor Fusion (temperature readings, sources)",
                        ),
                        selector.SelectOptionDict(
                            value="schedule",
                            label="Schedule Logic (active blocks, next change)",
                        ),
                        selector.SelectOptionDict(
                            value="heating",
                            label="Heating Controller (hysteresis, trend, cycle guard)",
                        ),
                        selector.SelectOptionDict(
                            value="calibration",
                            label="Calibration (TRV offset, boost, adaptive)",
                        ),
                        selector.SelectOptionDict(
                            value="early_start",
                            label="Early Start (heating rate, learning, preheating)",
                        ),
                        selector.SelectOptionDict(
                            value="rooms",
                            label="Room Logic (heating decisions, targets)",
                        ),
                        selector.SelectOptionDict(
                            value="hub", label="Hub Logic (mode changes, coordination)"
                        ),
                        selector.SelectOptionDict(
                            value="panel", label="Schedule Panel"
                        ),
                        selector.SelectOptionDict(value="ui", label="User Interface"),
                        selector.SelectOptionDict(
                            value="cards", label="Dashboard Cards"
                        ),
                        selector.SelectOptionDict(
                            value="verbose",
                            label="VERBOSE (Enable ALL - very detailed)",
                        ),
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        )

        return self.async_show_form(
            step_id="debug_settings",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_room_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room basic settings."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)

            # Remove empty optional fields instead of storing "" or []
            for key, value in user_input.items():
                if value in ("", [], None, "default"):
                    new_data.pop(key, None)
                else:
                    new_data[key] = value

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            # Save feature settings if hysteresis, PID, or heating curve changed
            if (
                CONF_HYSTERESIS in user_input
                or CONF_USE_PID_CONTROL in user_input
                or CONF_USE_HEATING_CURVE in user_input
            ):
                coordinator = (
                    self.hass.data[DOMAIN]
                    .get(self.config_entry.entry_id, {})
                    .get("coordinator")
                )
                if coordinator and hasattr(coordinator, "async_save_feature_settings"):
                    # Update hysteresis in controller
                    if CONF_HYSTERESIS in user_input:
                        coordinator.heating_controller.set_hysteresis(
                            user_input[CONF_HYSTERESIS]
                        )

                    # Update PID settings if changed
                    if CONF_USE_PID_CONTROL in user_input:
                        from .core.control import (
                            PIDConfig,
                            PIDHeatingController,
                            HeatingController,
                        )

                        use_pid = user_input[CONF_USE_PID_CONTROL]
                        current_is_pid = isinstance(
                            coordinator.heating_controller, PIDHeatingController
                        )

                        if use_pid and not current_is_pid:
                            # Switch to PID controller
                            pid_config = PIDConfig(
                                kp=user_input.get(CONF_PID_KP, DEFAULT_PID_KP),
                                ki=user_input.get(CONF_PID_KI, DEFAULT_PID_KI),
                                kd=user_input.get(CONF_PID_KD, DEFAULT_PID_KD),
                            )
                            coordinator.heating_controller = PIDHeatingController(
                                pid_config
                            )
                            coordinator.heating_controller.set_hysteresis(
                                user_input.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
                            )
                        elif not use_pid and current_is_pid:
                            # Switch to basic controller
                            hysteresis = coordinator.heating_controller.hysteresis
                            coordinator.heating_controller = HeatingController(
                                hysteresis=hysteresis
                            )
                        elif use_pid and current_is_pid:
                            # Update PID parameters
                            coordinator.heating_controller.config.kp = user_input.get(
                                CONF_PID_KP, DEFAULT_PID_KP
                            )
                            coordinator.heating_controller.config.ki = user_input.get(
                                CONF_PID_KI, DEFAULT_PID_KI
                            )
                            coordinator.heating_controller.config.kd = user_input.get(
                                CONF_PID_KD, DEFAULT_PID_KD
                            )

                    # Update heating curve settings if changed
                    if CONF_USE_HEATING_CURVE in user_input:
                        from .core.heating_curve import HeatingCurve, HeatingCurveConfig

                        use_curve = user_input[CONF_USE_HEATING_CURVE]

                        if use_curve and coordinator.heating_curve is None:
                            # Enable heating curve
                            curve_config = HeatingCurveConfig(
                                curve_slope=user_input.get(
                                    CONF_HEATING_CURVE_SLOPE,
                                    DEFAULT_HEATING_CURVE_SLOPE,
                                ),
                            )
                            coordinator.heating_curve = HeatingCurve(curve_config)
                        elif not use_curve and coordinator.heating_curve is not None:
                            # Disable heating curve
                            coordinator.heating_curve = None
                        elif use_curve and coordinator.heating_curve is not None:
                            # Update heating curve slope
                            coordinator.heating_curve.config.curve_slope = (
                                user_input.get(
                                    CONF_HEATING_CURVE_SLOPE,
                                    DEFAULT_HEATING_CURVE_SLOPE,
                                )
                            )

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
        schema_dict[
            vol.Required(
                CONF_TRV_ENTITIES,
                default=current_data.get(CONF_TRV_ENTITIES, []),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="climate",
                multiple=True,
            )
        )

        # Add optional fields with conditional defaults
        main_temp = current_data.get(CONF_MAIN_TEMP_SENSOR)
        schema_dict[
            vol.Optional(
                CONF_MAIN_TEMP_SENSOR,
                description={"suggested_value": main_temp} if main_temp else None,
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        humidity_sensor = current_data.get(CONF_HUMIDITY_SENSOR)
        schema_dict[
            vol.Optional(
                CONF_HUMIDITY_SENSOR,
                description={"suggested_value": humidity_sensor}
                if humidity_sensor
                else None,
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="humidity",
            )
        )

        schema_dict[
            vol.Optional(
                CONF_WINDOW_SENSORS,
                default=current_data.get(CONF_WINDOW_SENSORS, []),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="binary_sensor",
                device_class=["door", "window", "opening"],
                multiple=True,
            )
        )

        outdoor_sensor = current_data.get(CONF_OUTDOOR_SENSOR)
        schema_dict[
            vol.Optional(
                CONF_OUTDOOR_SENSOR,
                description={"suggested_value": outdoor_sensor}
                if outdoor_sensor
                else None,
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        # Override Timeout (Room level, includes "always" option)
        current_override_timeout = current_data.get(CONF_OVERRIDE_TIMEOUT, "default")
        schema_dict[
            vol.Optional(
                CONF_OVERRIDE_TIMEOUT,
                default=current_override_timeout,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="default", label="Use hub setting"),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEVER,
                        label="Never (manual changes stay forever)",
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_1H, label="1 hour"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_2H, label="2 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_3H, label="3 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_4H, label="4 hours"
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEXT_BLOCK,
                        label="Until next schedule block",
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_NEXT_DAY,
                        label="Until next day (midnight)",
                    ),
                    selector.SelectOptionDict(
                        value=OVERRIDE_TIMEOUT_ALWAYS,
                        label="Always use schedule (no manual override)",
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        # Hysteresis
        current_hysteresis = current_data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        schema_dict[
            vol.Optional(
                CONF_HYSTERESIS,
                default=current_hysteresis,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_HYSTERESIS,
                max=MAX_HYSTERESIS,
                step=0.1,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # PID Control
        current_use_pid = current_data.get(
            CONF_USE_PID_CONTROL, DEFAULT_USE_PID_CONTROL
        )
        schema_dict[
            vol.Optional(
                CONF_USE_PID_CONTROL,
                default=current_use_pid,
            )
        ] = selector.BooleanSelector()

        # PID Parameters (only shown if PID is enabled, but always available in schema)
        current_pid_kp = current_data.get(CONF_PID_KP, DEFAULT_PID_KP)
        schema_dict[
            vol.Optional(
                CONF_PID_KP,
                default=current_pid_kp,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1,
                max=5.0,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        current_pid_ki = current_data.get(CONF_PID_KI, DEFAULT_PID_KI)
        schema_dict[
            vol.Optional(
                CONF_PID_KI,
                default=current_pid_ki,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.001,
                max=0.1,
                step=0.001,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        current_pid_kd = current_data.get(CONF_PID_KD, DEFAULT_PID_KD)
        schema_dict[
            vol.Optional(
                CONF_PID_KD,
                default=current_pid_kd,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=1.0,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        # Moes TRV Mode (Use HVAC Off for Low Temperatures)
        current_use_hvac_off = current_data.get(
            CONF_USE_HVAC_OFF_FOR_LOW_TEMP, DEFAULT_USE_HVAC_OFF_FOR_LOW_TEMP
        )
        schema_dict[
            vol.Optional(
                CONF_USE_HVAC_OFF_FOR_LOW_TEMP,
                default=current_use_hvac_off,
            )
        ] = selector.BooleanSelector()

        # Multi-Room Heat Coupling (Phase 3.2)
        current_use_coupling = current_data.get(
            CONF_USE_ROOM_COUPLING, DEFAULT_USE_ROOM_COUPLING
        )
        schema_dict[
            vol.Optional(
                CONF_USE_ROOM_COUPLING,
                default=current_use_coupling,
            )
        ] = selector.BooleanSelector()

        # Adjacent Rooms (for coupling)
        current_adjacent = current_data.get(CONF_ADJACENT_ROOMS, [])
        # Get list of other rooms for selection
        other_rooms = self._get_other_room_names()
        if other_rooms:
            schema_dict[
                vol.Optional(
                    CONF_ADJACENT_ROOMS,
                    default=current_adjacent,
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=other_rooms,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        # Coupling Strength
        current_coupling_strength = current_data.get(
            CONF_COUPLING_STRENGTH, DEFAULT_COUPLING_STRENGTH
        )
        schema_dict[
            vol.Optional(
                CONF_COUPLING_STRENGTH,
                default=current_coupling_strength,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1,
                max=1.0,
                step=0.1,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )

        # Away Temperature (per-room)
        current_away_temp = current_data.get(
            CONF_AWAY_TEMPERATURE, DEFAULT_AWAY_TEMPERATURE
        )
        schema_dict[
            vol.Optional(
                CONF_AWAY_TEMPERATURE,
                default=current_away_temp,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10.0,
                max=25.0,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        return self.async_show_form(
            step_id="room_config",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": (
                    "Room Configuration:\n\n"
                    "• Override Timeout: How long manual TRV changes override schedules (leave empty to use hub setting)\n"
                    "• Hysteresis: Temperature deadband to prevent rapid cycling (°C)\n"
                    "• PID Control: Enable advanced PID controller for smoother temperature regulation\n"
                    "• Use HVAC Off for Low Temp: Enable for Moes TRVs - uses HVAC mode 'off' instead of low temperature\n"
                    "• Room Coupling: Reduce heating when neighbors are actively heating\n"
                    "• Adjacent Rooms: Select rooms that share walls with this room\n"
                    "• Away Temperature: Target temperature when nobody is home (default 17°C)\n"
                    "• Coupling Strength: How much to adjust for neighbor heating (0.1 = subtle, 1.0 = strong)\n\n"
                    f"Hub Defaults: Hysteresis={DEFAULT_HYSTERESIS}°C"
                )
            },
        )

    def _get_other_room_names(self) -> list[str]:
        """Get list of other room names for adjacent room selection."""
        current_room = self.config_entry.data.get(CONF_ROOM_NAME, "")
        rooms = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_HUB, False):
                continue  # Skip hub
            room_name = entry.data.get(CONF_ROOM_NAME, "")
            if room_name and room_name != current_room:
                rooms.append(room_name)
        return sorted(rooms)
