"""Options flow for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BOILER_TEMP_SENSOR,
    CONF_DEBUG_CALIBRATION,
    CONF_DEBUG_CARDS,
    CONF_DEBUG_EARLY_START,
    CONF_DEBUG_HEATING,
    CONF_DEBUG_HUB,
    CONF_DEBUG_PANEL,
    CONF_DEBUG_ROOMS,
    CONF_DEBUG_SCHEDULE,
    CONF_DEBUG_SENSORS,
    CONF_DEBUG_TRV,
    CONF_DEBUG_UI,
    CONF_DEBUG_VERBOSE,
    CONF_DHW_TEMP_SENSOR,
    CONF_HEATING_CURVE_SLOPE,
    CONF_HUB,
    CONF_HUMIDITY_SENSOR,
    CONF_HYSTERESIS,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_PERSON_ENTITIES,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_USE_HEATING_CURVE,
    CONF_USE_PID_CONTROL,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    DEFAULT_HEATING_CURVE_SLOPE,
    DEFAULT_HUB_MODES,
    DEFAULT_HYSTERESIS,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
    MAX_CUSTOM_MODES,
)
from .schedule_editor_flow import ScheduleEditorMixin

_LOGGER = logging.getLogger(__name__)


class TaDIYOptionsFlowHandler(ScheduleEditorMixin, OptionsFlow):
    """Handle options flow for TaDIY."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        # Call super().__init__() to properly initialize DataEntryFlow/FlowHandler state
        try:
            super().__init__(config_entry)
        except TypeError:
            super().__init__()
        self._entry = config_entry
        self._config_entry = config_entry
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
        """Configure hub-level entity pickers (weather, outdoor, boiler, dhw, persons)."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)

            # Remove empty optional fields
            for key in [
                CONF_WEATHER_ENTITY,
                CONF_OUTDOOR_SENSOR,
                CONF_PERSON_ENTITIES,
                CONF_BOILER_TEMP_SENSOR,
                CONF_DHW_TEMP_SENSOR,
            ]:
                value = user_input.get(key)
                if value in ("", [], None):
                    new_data.pop(key, None)
                else:
                    new_data[key] = value

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Trigger panel update by reloading entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Get current settings
        current_data = self.config_entry.data
        current_weather = current_data.get(CONF_WEATHER_ENTITY, "")
        current_outdoor_sensor = current_data.get(CONF_OUTDOOR_SENSOR, "")
        current_boiler_sensor = current_data.get(CONF_BOILER_TEMP_SENSOR, "")
        current_dhw_sensor = current_data.get(CONF_DHW_TEMP_SENSOR, "")
        current_persons = current_data.get(CONF_PERSON_ENTITIES, [])

        schema_dict = {}

        schema_dict[
            vol.Optional(
                CONF_WEATHER_ENTITY,
                description={"suggested_value": current_weather},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="weather",
            )
        )

        schema_dict[
            vol.Optional(
                CONF_OUTDOOR_SENSOR,
                description={"suggested_value": current_outdoor_sensor},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        schema_dict[
            vol.Optional(
                CONF_BOILER_TEMP_SENSOR,
                description={"suggested_value": current_boiler_sensor},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
            )
        )

        schema_dict[
            vol.Optional(
                CONF_DHW_TEMP_SENSOR,
                description={"suggested_value": current_dhw_sensor},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
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

            # List of optional entity fields that should be removable
            optional_entity_fields = [
                CONF_MAIN_TEMP_SENSOR,
                CONF_HUMIDITY_SENSOR,
            ]
            # Remove any legacy room-level weather/outdoor settings (now Hub-only)
            new_data.pop(CONF_OUTDOOR_SENSOR, None)
            new_data.pop(CONF_WEATHER_ENTITY, None)

            # Debug logging
            _LOGGER.debug(
                "Room config update - user_input keys: %s", list(user_input.keys())
            )
            for field in optional_entity_fields:
                if field in user_input:
                    _LOGGER.debug(
                        "Optional field %s in user_input: %s", field, user_input[field]
                    )

            # Process all user input
            for key, value in user_input.items():
                if value in ("", [], None, "default"):
                    # Remove empty values
                    new_data.pop(key, None)
                    _LOGGER.debug("Removing empty field: %s", key)
                else:
                    new_data[key] = value

            # Handle cleared optional entity fields: when an EntitySelector is
            # cleared, HA omits the key from user_input entirely. If the key was
            # in the old data but NOT in user_input, the user cleared it.
            for field_key in optional_entity_fields:
                if field_key not in user_input and field_key in new_data:
                    _LOGGER.debug(
                        "Removing cleared optional field: %s (was %s)",
                        field_key,
                        new_data[field_key],
                    )
                    new_data.pop(field_key, None)

            _LOGGER.debug("Final new_data keys: %s", list(new_data.keys()))

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
                            HeatingController,
                            PIDConfig,
                            PIDHeatingController,
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

        # Add optional fields - only set default if there's a value
        main_temp = current_data.get(CONF_MAIN_TEMP_SENSOR)
        if main_temp:
            schema_dict[vol.Optional(CONF_MAIN_TEMP_SENSOR, default=main_temp)] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="temperature",
                    )
                )
            )
        else:
            schema_dict[vol.Optional(CONF_MAIN_TEMP_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            )

        humidity_sensor = current_data.get(CONF_HUMIDITY_SENSOR)
        if humidity_sensor:
            schema_dict[vol.Optional(CONF_HUMIDITY_SENSOR, default=humidity_sensor)] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="humidity",
                    )
                )
            )
        else:
            schema_dict[vol.Optional(CONF_HUMIDITY_SENSOR)] = selector.EntitySelector(
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

        return self.async_show_form(
            step_id="room_config",
            data_schema=vol.Schema(schema_dict),
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
