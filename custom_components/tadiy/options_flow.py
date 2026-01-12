"""Options flow for TaDIY integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DONT_HEAT_BELOW,
    CONF_EARLY_START_MAX,
    CONF_EARLY_START_OFFSET,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_EARLY_START_MAX,
    CONF_GLOBAL_EARLY_START_OFFSET,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_HUB,
    CONF_LEARN_HEATING_RATE,
    CONF_MAIN_TEMP_SENSOR,
    CONF_MAX_HEATING_RATE,
    CONF_MIN_HEATING_RATE,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_TARGET_TEMP_STEP,
    CONF_TOLERANCE,
    CONF_TRV_ENTITIES,
    CONF_USE_EARLY_START,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_MAX_HEATING_RATE,
    DEFAULT_MIN_HEATING_RATE,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    HUB_MODE_HOMEOFFICE,
    HUB_MODE_NORMAL,
    HUB_MODE_PARTY,
    HUB_MODE_VACATION,
    SCHEDULE_HOMEOFFICE,
    SCHEDULE_NORMAL_WEEKDAY,
    SCHEDULE_NORMAL_WEEKEND,
    SCHEDULE_PARTY,
    SCHEDULE_VACATION,
)

_LOGGER = logging.getLogger(__name__)


def convert_seconds_to_duration(seconds: int | None) -> dict[str, int] | None:
    """Convert seconds to duration dict."""
    if seconds is None:
        return None
    return {
        "hours": seconds // 3600,
        "minutes": (seconds % 3600) // 60,
        "seconds": seconds % 60,
    }


def convert_duration_to_seconds(duration: dict[str, int] | None) -> int | None:
    """Convert duration dict to seconds."""
    if duration is None:
        return None
    return (
        duration.get("hours", 0) * 3600
        + duration.get("minutes", 0) * 60
        + duration.get("seconds", 0)
    )


class TaDIYOptionsFlowHandler(OptionsFlow):
    """Handle options flow for TaDIY."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._entry = config_entry
        self._current_schedule: str | None = None
    
    @property
    def config_entry(self) -> ConfigEntry:
        """Return config entry."""
        return self._entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - router between Hub and Room."""
        is_hub = self.config_entry.data.get(CONF_HUB, False)
        
        if is_hub:
            return await self.async_step_init_hub(user_input)
        else:
            return await self.async_step_init_room(user_input)

    async def async_step_init_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Hub options."""
        # Count rooms
        room_count = len(
            [
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if not entry.data.get(CONF_HUB, False)
            ]
        )

        return self.async_show_menu(
            step_id="init_hub",
            menu_options=["global_defaults", "hub_mode"],
            description_placeholders={"room_count": str(room_count)},
        )

    async def async_step_init_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Room options."""
        room_name = self.config_entry.data.get(CONF_ROOM_NAME, "Unknown")
        
        return self.async_show_menu(
            step_id="init_room",
            menu_options=["room_details", "schedules", "learning"],
            description_placeholders={"room_name": room_name},
        )

    # ========== HUB OPTIONS ==========

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure global defaults."""
        if user_input is not None:
            # Convert durations
            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_OPEN_TIMEOUT), dict):
                user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_OPEN_TIMEOUT]
                )
            if isinstance(user_input.get(CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT), dict):
                user_input[
                    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT
                ] = convert_duration_to_seconds(
                    user_input[CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT]
                )

            # Update config entry data (not options, as these are global settings)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            
            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                        default=convert_seconds_to_duration(
                            current_data.get(
                                CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                                DEFAULT_WINDOW_OPEN_TIMEOUT,
                            )
                        ),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                        default=convert_seconds_to_duration(
                            current_data.get(
                                CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                                DEFAULT_WINDOW_CLOSE_TIMEOUT,
                            )
                        ),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_GLOBAL_DONT_HEAT_BELOW,
                        default=current_data.get(
                            CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW
                        ),
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
                        default=current_data.get(
                            CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START
                        ),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_LEARN_HEATING_RATE,
                        default=current_data.get(
                            CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
                        ),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_GLOBAL_EARLY_START_OFFSET,
                        default=current_data.get(
                            CONF_GLOBAL_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET
                        ),
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
                        default=current_data.get(
                            CONF_GLOBAL_EARLY_START_MAX, DEFAULT_EARLY_START_MAX
                        ),
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

    async def async_step_hub_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure hub mode."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_mode = self.config_entry.options.get("hub_mode", HUB_MODE_NORMAL)

        return self.async_show_form(
            step_id="hub_mode",
            data_schema=vol.Schema(
                {
                    vol.Required("hub_mode", default=current_mode): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                HUB_MODE_NORMAL,
                                HUB_MODE_HOMEOFFICE,
                                HUB_MODE_VACATION,
                                HUB_MODE_PARTY,
                            ],
                            translation_key="hub_mode",
                        )
                    ),
                }
            ),
        )

    # ========== ROOM OPTIONS ==========

    async def async_step_room_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room details."""
        if user_input is not None:
            # Convert durations
            if isinstance(user_input.get(CONF_WINDOW_OPEN_TIMEOUT), dict):
                user_input[CONF_WINDOW_OPEN_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_WINDOW_OPEN_TIMEOUT]
                )
            if isinstance(user_input.get(CONF_WINDOW_CLOSE_TIMEOUT), dict):
                user_input[CONF_WINDOW_CLOSE_TIMEOUT] = convert_duration_to_seconds(
                    user_input[CONF_WINDOW_CLOSE_TIMEOUT]
                )

            # Update config entry data
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            
            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data
        room_name = current_data.get(CONF_ROOM_NAME, "Unknown")

        return self.async_show_form(
            step_id="room_details",
            data_schema=vol.Schema(
                {
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
                            device_class="window",
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
                    vol.Optional(
                        CONF_WINDOW_OPEN_TIMEOUT,
                        description={"suggested_value": None},
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_WINDOW_CLOSE_TIMEOUT,
                        description={"suggested_value": None},
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(enable_day=False)
                    ),
                    vol.Optional(
                        CONF_DONT_HEAT_BELOW,
                        description={"suggested_value": None},
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
                        CONF_TARGET_TEMP_STEP,
                        default=current_data.get(CONF_TARGET_TEMP_STEP, DEFAULT_TARGET_TEMP_STEP),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=2.0,
                            step=0.1,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_TOLERANCE,
                        default=current_data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=2.0,
                            step=0.1,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_USE_EARLY_START,
                        description={"suggested_value": None},
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_LEARN_HEATING_RATE,
                        description={"suggested_value": None},
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_EARLY_START_OFFSET,
                        description={"suggested_value": None},
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
                        CONF_EARLY_START_MAX,
                        description={"suggested_value": None},
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
            description_placeholders={"room_name": room_name},
        )

    async def async_step_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show schedule selection menu."""
        return self.async_show_menu(
            step_id="schedules",
            menu_options=[
                "schedule_normal_weekday",
                "schedule_normal_weekend",
                "schedule_homeoffice",
                "schedule_vacation",
                "schedule_party",
            ],
        )

    async def async_step_schedule_normal_weekday(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit normal weekday schedule."""
        return await self._handle_schedule_edit(
            SCHEDULE_NORMAL_WEEKDAY, "Normal - Wochentag", user_input
        )

    async def async_step_schedule_normal_weekend(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit normal weekend schedule."""
        return await self._handle_schedule_edit(
            SCHEDULE_NORMAL_WEEKEND, "Normal - Wochenende", user_input
        )

    async def async_step_schedule_homeoffice(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit homeoffice schedule."""
        return await self._handle_schedule_edit(
            SCHEDULE_HOMEOFFICE, "Homeoffice", user_input
        )

    async def async_step_schedule_vacation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit vacation schedule."""
        return await self._handle_schedule_edit(
            SCHEDULE_VACATION, "Urlaub", user_input
        )

    async def async_step_schedule_party(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit party schedule."""
        return await self._handle_schedule_edit(SCHEDULE_PARTY, "Party", user_input)

    async def _handle_schedule_edit(
        self, schedule_key: str, schedule_name: str, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Handle schedule editing."""
        if user_input is not None:
            # Parse schedule entries
            # This is simplified - you'll need proper validation
            schedule_data = {schedule_key: user_input}
            return self.async_create_entry(title="", data=schedule_data)

        # Load current schedule
        current_schedule = self.config_entry.options.get(schedule_key, [])

        # Build schema for up to 6 entries
        schema_dict = {}
        for i in range(1, 7):
            default_val = ""
            if i <= len(current_schedule):
                entry = current_schedule[i - 1]
                default_val = f"{entry.get('time', '')} - {entry.get('temperature', '')}"
            
            schema_dict[
                vol.Optional(f"schedule_entry_{i}", default=default_val)
            ] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"schedule_name": schedule_name},
        )

    async def async_step_learning(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure learning settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_data = self.config_entry.data
        current_options = self.config_entry.options
        room_name = current_data.get(CONF_ROOM_NAME, "Unknown")

        # Get current heating rate from coordinator if available
        coordinator_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        current_heating_rate = DEFAULT_MIN_HEATING_RATE
        if coordinator_data:
            coordinator = coordinator_data.get("coordinator")
            if coordinator and hasattr(coordinator, "data"):
                current_heating_rate = coordinator.data.get("heating_rate", DEFAULT_MIN_HEATING_RATE)

        return self.async_show_form(
            step_id="learning",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MIN_HEATING_RATE,
                        default=current_options.get(CONF_MIN_HEATING_RATE, DEFAULT_MIN_HEATING_RATE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=5.0,
                            step=0.1,
                            unit_of_measurement="°C/h",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_HEATING_RATE,
                        default=current_options.get(CONF_MAX_HEATING_RATE, DEFAULT_MAX_HEATING_RATE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.5,
                            max=10.0,
                            step=0.5,
                            unit_of_measurement="°C/h",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        "current_heating_rate",
                        default=round(current_heating_rate, 2),
                        description={"suggested_value": round(current_heating_rate, 2)},
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=10.0,
                            step=0.1,
                            unit_of_measurement="°C/h",
                            mode=selector.NumberSelectorMode.BOX,
                            disabled=True,
                        )
                    ),
                }
            ),
            description_placeholders={"room_name": room_name},
        )