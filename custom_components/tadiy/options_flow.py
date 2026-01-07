"""Config flow for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
import voluptuous as vol

from .const import (
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_LEARN_HEATING_RATE,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_TARGET_TEMP_STEP,
    CONF_TOLERANCE,
    CONF_TRV_ENTITIES,
    CONF_USE_EARLY_START,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKDAY,
    SCHEDULE_TYPE_WEEKEND,
    TARGET_TEMP_STEP_OPTIONS,
    TOLERANCE_OPTIONS,
)
from .models.schedule import RoomSchedule
from .ui.schedule_editor import ScheduleEditor

_LOGGER = logging.getLogger(__name__)


class TaDIYOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle TaDIY options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.schedule_editor = ScheduleEditor()
        
        # State for multi-step flows
        self.current_room_index: int | None = None
        self.current_room_data: dict[str, Any] = {}
        self.schedule_blocks: list[dict[str, Any]] = []
        self.current_schedule_type: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "global_defaults",
                "add_room",
                "edit_room",
                "delete_room",
            ],
        )

    async def async_step_global_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure global default values."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                    default=self.options.get(
                        CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                    default=self.options.get(
                        CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_GLOBAL_DONT_HEAT_BELOW,
                    default=self.options.get(
                        CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_GLOBAL_USE_EARLY_START,
                    default=self.options.get(
                        CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START
                    ),
                ): cv.boolean,
                vol.Optional(
                    CONF_GLOBAL_LEARN_HEATING_RATE,
                    default=self.options.get(
                        CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
                    ),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="global_defaults",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        if user_input is not None:
            self.current_room_data = user_input
            return await self.async_step_room_details()

        schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME): cv.string,
            }
        )

        return self.async_show_form(
            step_id="add_room",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_edit_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select room to edit."""
        rooms = self.options.get(CONF_ROOMS, [])
        
        if not rooms:
            return self.async_abort(reason="no_rooms")

        if user_input is not None:
            room_name = user_input["room"]
            for idx, room in enumerate(rooms):
                if room[CONF_ROOM_NAME] == room_name:
                    self.current_room_index = idx
                    self.current_room_data = dict(room)
                    break
            return await self.async_step_edit_room_menu()

        room_names = [room[CONF_ROOM_NAME] for room in rooms]
        schema = vol.Schema(
            {
                vol.Required("room"): vol.In(room_names),
            }
        )

        return self.async_show_form(
            step_id="edit_room",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_edit_room_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Menu for editing room."""
        return self.async_show_menu(
            step_id="edit_room_menu",
            menu_options=[
                "room_details",
                "edit_schedule",
                "save_room",
            ],
        )

    async def async_step_room_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure room details."""
        if user_input is not None:
            self.current_room_data.update(user_input)
            
            # If adding new room, go directly to save
            if self.current_room_index is None:
                return await self.async_step_save_room()
            
            # If editing, return to edit menu
            return await self.async_step_edit_room_menu()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRV_ENTITIES,
                    default=self.current_room_data.get(CONF_TRV_ENTITIES, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Required(
                    CONF_MAIN_TEMP_SENSOR,
                    default=self.current_room_data.get(CONF_MAIN_TEMP_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_WINDOW_SENSORS,
                    default=self.current_room_data.get(CONF_WINDOW_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="binary_sensor", multiple=True
                    )
                ),
                vol.Optional(
                    CONF_OUTDOOR_SENSOR,
                    default=self.current_room_data.get(CONF_OUTDOOR_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_WINDOW_OPEN_TIMEOUT,
                    default=self.current_room_data.get(
                        CONF_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_WINDOW_CLOSE_TIMEOUT,
                    default=self.current_room_data.get(
                        CONF_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_DONT_HEAT_BELOW_OUTDOOR,
                    default=self.current_room_data.get(
                        CONF_DONT_HEAT_BELOW_OUTDOOR, DEFAULT_DONT_HEAT_BELOW
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_TARGET_TEMP_STEP,
                    default=self.current_room_data.get(
                        CONF_TARGET_TEMP_STEP, DEFAULT_TARGET_TEMP_STEP
                    ),
                ): vol.In(TARGET_TEMP_STEP_OPTIONS),
                vol.Optional(
                    CONF_TOLERANCE,
                    default=self.current_room_data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE),
                ): vol.In(TOLERANCE_OPTIONS),
                vol.Optional(
                    CONF_USE_EARLY_START,
                    default=self.current_room_data.get(
                        CONF_USE_EARLY_START, DEFAULT_USE_EARLY_START
                    ),
                ): cv.boolean,
                vol.Optional(
                    CONF_LEARN_HEATING_RATE,
                    default=self.current_room_data.get(
                        CONF_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
                    ),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="room_details",
            data_schema=schema,
            last_step=False,
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which schedule to edit."""
        return self.async_show_menu(
            step_id="edit_schedule",
            menu_options=[
                "schedule_normal_weekday",
                "schedule_normal_weekend",
                "schedule_homeoffice",
            ],
        )

    async def async_step_schedule_normal_weekday(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit Normal mode weekday schedule."""
        self.current_schedule_type = SCHEDULE_TYPE_WEEKDAY
        return await self._show_schedule_editor("Normal - Weekday (Mo-Fr)")

    async def async_step_schedule_normal_weekend(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit Normal mode weekend schedule."""
        self.current_schedule_type = SCHEDULE_TYPE_WEEKEND
        return await self._show_schedule_editor("Normal - Weekend (Sa-So)")

    async def async_step_schedule_homeoffice(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit Homeoffice mode schedule."""
        self.current_schedule_type = SCHEDULE_TYPE_DAILY
        return await self._show_schedule_editor("Homeoffice (Mo-So)")

    async def _show_schedule_editor(self, title: str) -> FlowResult:
        """Show schedule editor with current blocks."""
        # Load existing schedule from storage
        coordinator = self.hass.data[DOMAIN][self._config_entry.entry_id]["coordinator"]
        room_name = self.current_room_data[CONF_ROOM_NAME]
        
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        
        if room_schedule:
            if self.current_schedule_type == SCHEDULE_TYPE_WEEKDAY:
                day_schedule = room_schedule.normal_weekday
            elif self.current_schedule_type == SCHEDULE_TYPE_WEEKEND:
                day_schedule = room_schedule.normal_weekend
            else:  # DAILY
                day_schedule = room_schedule.homeoffice_daily
        else:
            day_schedule = None

        self.schedule_blocks = self.schedule_editor.day_schedule_to_blocks(day_schedule)

        return self.async_show_menu(
            step_id=f"schedule_editor_{self.current_schedule_type}",
            menu_options=[
                "schedule_add_block",
                "schedule_view_blocks",
                "schedule_save",
            ],
            description_placeholders={"title": title},
        )

    async def async_step_schedule_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new schedule block."""
        errors = {}
        
        if user_input is not None:
            # Validate time inputs
            start_time = self.schedule_editor.parse_time_input(user_input["start_time"])
            end_time = self.schedule_editor.parse_time_input(user_input["end_time"])
            
            if not start_time:
                errors["start_time"] = "invalid_time"
            if not end_time:
                errors["end_time"] = "invalid_time"
            
            if not errors:
                # Add block
                new_block = {
                    "start": start_time,
                    "end": end_time,
                    "temp": user_input["temperature"],
                }
                self.schedule_blocks.append(new_block)
                
                # Sort blocks
                self.schedule_blocks.sort(key=lambda b: b["start"])
                
                # Return to editor
                return await self._show_schedule_editor(
                    f"Schedule {self.current_schedule_type}"
                )

        schema = self.schedule_editor.get_add_block_schema(self.schedule_blocks)
        
        # Render timeline
        timeline = self.schedule_editor.render_timeline(self.schedule_blocks)

        return self.async_show_form(
            step_id="schedule_add_block",
            data_schema=schema,
            errors=errors,
            description_placeholders={"timeline": timeline},
            last_step=False,
        )

    async def async_step_schedule_view_blocks(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """View and delete blocks."""
        if user_input is not None:
            if "delete_block" in user_input:
                block_index = int(user_input["delete_block"])
                if 0 <= block_index < len(self.schedule_blocks):
                    del self.schedule_blocks[block_index]
                
                return await self._show_schedule_editor(
                    f"Schedule {self.current_schedule_type}"
                )

        # Build block list for selection
        block_options = {}
        for idx, block in enumerate(self.schedule_blocks):
            temp_str = (
                block["temp"]
                if isinstance(block["temp"], str)
                else f"{block['temp']}°C"
            )
            block_options[str(idx)] = (
                f"{block['start']} - {block['end']}: {temp_str}"
            )

        if not block_options:
            return await self._show_schedule_editor(
                f"Schedule {self.current_schedule_type}"
            )

        schema = vol.Schema(
            {
                vol.Optional("delete_block"): vol.In(block_options),
            }
        )

        timeline = self.schedule_editor.render_timeline(self.schedule_blocks)

        return self.async_show_form(
            step_id="schedule_view_blocks",
            data_schema=schema,
            description_placeholders={"timeline": timeline},
            last_step=False,
        )

    async def async_step_schedule_save(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Save schedule."""
        # Validate blocks
        errors_list = self.schedule_editor.validate_blocks(self.schedule_blocks)
        
        if errors_list:
            # Show errors
            return self.async_show_form(
                step_id="schedule_save",
                data_schema=vol.Schema({}),
                errors={"base": "validation_failed"},
                description_placeholders={"errors": "\n".join(errors_list)},
                last_step=False,
            )

        # Convert blocks to DaySchedule
        try:
            day_schedule = self.schedule_editor.blocks_to_day_schedule(
                self.schedule_blocks, self.current_schedule_type
            )
        except Exception as err:
            _LOGGER.error("Failed to create schedule: %s", err)
            return self.async_show_form(
                step_id="schedule_save",
                data_schema=vol.Schema({}),
                errors={"base": "schedule_creation_failed"},
                last_step=False,
            )

        # Save to coordinator
        coordinator = self.hass.data[DOMAIN][self._config_entry.entry_id]["coordinator"]
        room_name = self.current_room_data[CONF_ROOM_NAME]

        # Get or create room schedule
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        if not room_schedule:
            room_schedule = RoomSchedule(room_name=room_name)

        # Update appropriate schedule
        if self.current_schedule_type == SCHEDULE_TYPE_WEEKDAY:
            room_schedule.normal_weekday = day_schedule
        elif self.current_schedule_type == SCHEDULE_TYPE_WEEKEND:
            room_schedule.normal_weekend = day_schedule
        else:  # DAILY
            room_schedule.homeoffice_daily = day_schedule

        # Save
        coordinator.update_room_schedule(room_name, room_schedule)
        await coordinator.async_save_schedules()

        _LOGGER.info("Schedule saved for room %s (%s)", room_name, self.current_schedule_type)

        # Return to edit schedule menu
        return await self.async_step_edit_schedule()

    async def async_step_save_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Save room configuration."""
        rooms = self.options.get(CONF_ROOMS, [])

        if self.current_room_index is not None:
            # Update existing room
            rooms[self.current_room_index] = self.current_room_data
        else:
            # Add new room
            rooms.append(self.current_room_data)

        self.options[CONF_ROOMS] = rooms

        # Reset state
        self.current_room_index = None
        self.current_room_data = {}

        return self.async_create_entry(title="", data=self.options)

    async def async_step_delete_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete a room."""
        rooms = self.options.get(CONF_ROOMS, [])
        
        if not rooms:
            return self.async_abort(reason="no_rooms")

        if user_input is not None:
            room_name = user_input["room"]
            rooms = [r for r in rooms if r[CONF_ROOM_NAME] != room_name]
            self.options[CONF_ROOMS] = rooms

            # Remove schedule
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id][
                "coordinator"
            ]
            if hasattr(coordinator.schedule_engine, 'remove_room_schedule'):
                coordinator.schedule_engine.remove_room_schedule(room_name)
            await coordinator.async_save_schedules()

            return self.async_create_entry(title="", data=self.options)

        room_names = [room[CONF_ROOM_NAME] for room in rooms]
        schema = vol.Schema(
            {
                vol.Required("room"): vol.In(room_names),
            }
        )

        return self.async_show_form(step_id="delete_room", data_schema=schema)
