"""Schedule editor flow for TaDIY."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ROOM_NAME,
    DOMAIN,
    HUB_MODE_NORMAL,
    MAX_TARGET_TEMP,
    MODE_MANUAL,
    MODE_OFF,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKDAY,
    SCHEDULE_TYPE_WEEKEND,
)
from .core.schedule_model import DaySchedule, RoomSchedule
from .schedule_storage import ScheduleStorageManager, ScheduleUIBlock
from .schedule_visualization import generate_timeline_html, generate_color_legend

_LOGGER = logging.getLogger(__name__)


class ScheduleEditorMixin:
    """Mixin for schedule editor functionality in options flow."""

    async def _get_room_coordinator(self):
        """Get room coordinator for this config entry."""
        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if not entry_data:
            return None
        return entry_data.get("coordinator")

    async def _get_hub_coordinator(self):
        """Get hub coordinator."""
        return self.hass.data[DOMAIN].get("hub_coordinator")

    async def _load_existing_schedule(self) -> None:
        """Load existing schedule from storage."""
        coordinator = await self._get_room_coordinator()
        if not coordinator or not coordinator.schedule_engine:
            return

        room_name = self.config_entry.data.get(CONF_ROOM_NAME)
        if not room_name:
            return

        # Get room schedule
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        if not room_schedule:
            return

        # Get appropriate day schedule based on mode and type
        day_schedule = None

        if self._selected_mode == HUB_MODE_NORMAL:
            if self._selected_schedule_type == SCHEDULE_TYPE_WEEKDAY:
                day_schedule = room_schedule.normal_weekday
            elif self._selected_schedule_type == SCHEDULE_TYPE_WEEKEND:
                day_schedule = room_schedule.normal_weekend
        elif self._selected_mode == "homeoffice":
            day_schedule = room_schedule.homeoffice_daily
        else:
            # Custom mode
            day_schedule = room_schedule.get_custom_schedule(self._selected_mode)

        if day_schedule:
            ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                day_schedule.blocks
            )
            self._editing_blocks = [b.to_dict() for b in ui_blocks]

    async def async_step_manage_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage schedules - select mode and type directly."""
        # Get hub coordinator to access available modes
        hub_coordinator = await self._get_hub_coordinator()
        if not hub_coordinator:
            return self.async_abort(reason="hub_not_found")

        available_modes = hub_coordinator.get_custom_modes()

        # Filter out modes that don't need schedules
        schedulable_modes = [
            mode for mode in available_modes if mode not in (MODE_MANUAL, MODE_OFF)
        ]

        if not schedulable_modes:
            return self.async_abort(reason="no_schedulable_modes")

        if user_input is not None:
            selected = user_input.get("schedule_selection")

            # Parse selection: "mode:type" or "mode" for daily
            if ":" in selected:
                self._selected_mode, self._selected_schedule_type = selected.split(":", 1)
            else:
                self._selected_mode = selected
                self._selected_schedule_type = SCHEDULE_TYPE_DAILY

            return await self.async_step_schedule_options()

        # Build flat list of all schedule options
        schedule_options = []

        for mode in schedulable_modes:
            if mode == HUB_MODE_NORMAL:
                # Normal has weekday and weekend
                schedule_options.append(
                    selector.SelectOptionDict(
                        value="normal:weekday",
                        label="Normal - Weekday (Mon-Fri)",
                    )
                )
                schedule_options.append(
                    selector.SelectOptionDict(
                        value="normal:weekend",
                        label="Normal - Weekend (Sat-Sun)",
                    )
                )
            else:
                # Other modes are daily
                display_name = ScheduleStorageManager.get_mode_display_name(mode, SCHEDULE_TYPE_DAILY)
                schedule_options.append(
                    selector.SelectOptionDict(
                        value=mode,
                        label=display_name,
                    )
                )

        return self.async_show_form(
            step_id="manage_schedules",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_selection"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=schedule_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={
                "room_name": self.config_entry.data.get(CONF_ROOM_NAME, "Unknown"),
            },
        )

    async def async_step_schedule_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose schedule options (edit, copy, use default)."""
        if not self._selected_mode or not self._selected_schedule_type:
            return await self.async_step_manage_schedules()

        # Check if this mode can use "Normal" as default
        show_use_default = self._selected_mode != HUB_MODE_NORMAL

        if user_input is not None:
            action = user_input.get("action")

            if action == "edit":
                # Load existing schedule or create default
                await self._load_existing_schedule()
                if not self._editing_blocks:
                    # Create default
                    default_blocks = ScheduleStorageManager.create_default_schedule(
                        self._selected_schedule_type
                    )
                    self._editing_blocks = [b.to_dict() for b in default_blocks]
                return await self.async_step_edit_schedule()
            elif action == "copy_mode":
                return await self.async_step_copy_from_mode()
            elif action == "copy_room":
                return await self.async_step_copy_from_room()
            elif action == "use_default":
                self._use_normal_default = True
                return await self._save_schedule_and_finish()

        # Build action options
        actions = [
            selector.SelectOptionDict(
                value="edit",
                label="Edit Schedule",
            ),
            selector.SelectOptionDict(
                value="copy_mode",
                label="Copy from Another Mode",
            ),
            selector.SelectOptionDict(
                value="copy_room",
                label="Copy from Another Room",
            ),
        ]

        if show_use_default:
            actions.append(
                selector.SelectOptionDict(
                    value="use_default",
                    label="Use Default (Normal)",
                )
            )

        display_name = ScheduleStorageManager.get_mode_display_name(
            self._selected_mode, self._selected_schedule_type
        )

        return self.async_show_form(
            step_id="schedule_options",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=actions,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={"schedule_name": display_name},
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit schedule with inline block editing."""
        if not self._selected_mode or not self._selected_schedule_type:
            return await self.async_step_manage_schedules()

        errors: dict[str, str] = {}

        if user_input is not None:
            # Handle different actions
            if "save" in user_input and user_input["save"]:
                # Validate and save
                ui_blocks = [
                    ScheduleUIBlock.from_dict(b) for b in self._editing_blocks
                ]
                is_valid, error = ScheduleStorageManager.validate_ui_blocks(ui_blocks)

                if is_valid:
                    return await self._save_schedule_and_finish()
                else:
                    errors["base"] = "validation_failed"
                    _LOGGER.error("Schedule validation failed: %s", error)

            elif "add_block" in user_input and user_input["add_block"]:
                # Add new empty block
                self._editing_blocks.append({
                    "start_time": "12:00",
                    "end_time": "18:00",
                    "temperature": 20.0,
                })
                # Continue editing

            elif "copy_from_mode" in user_input and user_input["copy_from_mode"]:
                return await self.async_step_copy_from_mode()

            elif "copy_from_room" in user_input and user_input["copy_from_room"]:
                return await self.async_step_copy_from_room()

            # Handle block updates and deletions
            updated_blocks = []
            for i, block in enumerate(self._editing_blocks):
                # Check if this block should be deleted
                delete_key = f"delete_{i}"
                if delete_key in user_input and user_input[delete_key]:
                    continue  # Skip this block (delete it)

                # Update block fields
                start_key = f"start_{i}"
                end_key = f"end_{i}"
                temp_key = f"temp_{i}"

                updated_block = {
                    "start_time": user_input.get(start_key, block["start_time"]),
                    "end_time": user_input.get(end_key, block["end_time"]),
                    "temperature": user_input.get(temp_key, block["temperature"]),
                }
                updated_blocks.append(updated_block)

            self._editing_blocks = updated_blocks

        # Generate timeline
        timeline_html = generate_timeline_html(self._editing_blocks)
        legend_html = generate_color_legend()

        display_name = ScheduleStorageManager.get_mode_display_name(
            self._selected_mode, self._selected_schedule_type
        )

        # Build schema for all blocks
        schema_dict = {}

        # Add fields for each block
        for i, block in enumerate(self._editing_blocks):
            # Start time
            schema_dict[vol.Required(f"start_{i}", default=block["start_time"])] = (
                selector.TimeSelector()
            )
            # End time
            schema_dict[vol.Required(f"end_{i}", default=block["end_time"])] = (
                selector.TimeSelector()
            )
            # Temperature (allow free decimal input, 0 for frost protection)
            temp_val = block["temperature"]
            if isinstance(temp_val, str) and temp_val.lower() == "off":
                temp_val = 0.0
            schema_dict[vol.Required(f"temp_{i}", default=temp_val)] = (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=MAX_TARGET_TEMP,
                        step=0.1,  # Free decimal input
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                    )
                )
            )
            # Delete button
            schema_dict[vol.Optional(f"delete_{i}", default=False)] = (
                selector.BooleanSelector()
            )

        # Add action buttons
        schema_dict[vol.Optional("add_block", default=False)] = (
            selector.BooleanSelector()
        )
        schema_dict[vol.Optional("copy_from_mode", default=False)] = (
            selector.BooleanSelector()
        )
        schema_dict[vol.Optional("copy_from_room", default=False)] = (
            selector.BooleanSelector()
        )
        schema_dict[vol.Optional("save", default=False)] = (
            selector.BooleanSelector()
        )

        description = (
            f"**{display_name}**\n\n"
            f"{timeline_html}\n\n"
            f"{legend_html}\n\n"
            f"**Blocks:**\n"
            f"Note: Enter 0°C for frost protection mode.\n\n"
        )

        # Add block descriptions
        sorted_blocks = sorted(enumerate(self._editing_blocks), key=lambda x: x[1]["start_time"])
        for idx, (original_idx, block) in enumerate(sorted_blocks, 1):
            temp_display = (
                "0°C (Frost)"
                if block["temperature"] == 0.0
                else f"{block['temperature']}°C"
            )
            description += f"Block #{idx}: {block['start_time']}-{block['end_time']} @ {temp_display}\n"

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "description": description,
            },
            errors=errors,
        )

    async def async_step_copy_from_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Copy schedule from another mode."""
        coordinator = await self._get_room_coordinator()
        if not coordinator or not coordinator.schedule_engine:
            return await self.async_step_edit_schedule()

        room_name = self.config_entry.data.get(CONF_ROOM_NAME)
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)

        if user_input is not None:
            source_mode_type = user_input.get("source_mode_type")

            # Copy blocks from source
            day_schedule = None
            if source_mode_type == "normal_weekday" and room_schedule:
                day_schedule = room_schedule.normal_weekday
            elif source_mode_type == "normal_weekend" and room_schedule:
                day_schedule = room_schedule.normal_weekend
            elif source_mode_type == "homeoffice" and room_schedule:
                day_schedule = room_schedule.homeoffice_daily
            else:
                # Custom mode
                day_schedule = room_schedule.get_custom_schedule(source_mode_type) if room_schedule else None

            if day_schedule:
                ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                    day_schedule.blocks
                )
                self._editing_blocks = [b.to_dict() for b in ui_blocks]

            return await self.async_step_edit_schedule()

        # Build available modes
        mode_options = []

        if room_schedule:
            if room_schedule.normal_weekday:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="normal_weekday",
                        label="Normal - Weekday (Mon-Fri)",
                    )
                )
            if room_schedule.normal_weekend:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="normal_weekend",
                        label="Normal - Weekend (Sat-Sun)",
                    )
                )
            if room_schedule.homeoffice_daily:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="homeoffice",
                        label="Homeoffice (daily)",
                    )
                )
            # Add custom schedules
            if room_schedule.custom_schedules:
                for mode, schedule in room_schedule.custom_schedules.items():
                    display_name = ScheduleStorageManager.get_mode_display_name(mode)
                    mode_options.append(
                        selector.SelectOptionDict(
                            value=mode,
                            label=f"{display_name} (daily)",
                        )
                    )

        if not mode_options:
            # No schedules to copy from
            return await self.async_step_edit_schedule()

        return self.async_show_form(
            step_id="copy_from_mode",
            data_schema=vol.Schema(
                {
                    vol.Required("source_mode_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=mode_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_copy_from_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Copy schedule from another room."""
        if user_input is not None:
            source_room = user_input.get("source_room")
            source_mode_type = user_input.get("source_mode_type")

            # Get source room coordinator
            for entry_id, entry_data in self.hass.data[DOMAIN].items():
                if entry_data.get("type") != "room":
                    continue

                entry = entry_data.get("entry")
                if not entry:
                    continue

                if entry.data.get(CONF_ROOM_NAME) == source_room:
                    source_coord = entry_data.get("coordinator")
                    if not source_coord or not source_coord.schedule_engine:
                        continue

                    source_schedule = source_coord.schedule_engine._room_schedules.get(source_room)
                    if not source_schedule:
                        continue

                    # Get the schedule
                    day_schedule = None
                    if source_mode_type == "normal_weekday":
                        day_schedule = source_schedule.normal_weekday
                    elif source_mode_type == "normal_weekend":
                        day_schedule = source_schedule.normal_weekend
                    elif source_mode_type == "homeoffice":
                        day_schedule = source_schedule.homeoffice_daily
                    else:
                        # Custom mode
                        day_schedule = source_schedule.get_custom_schedule(source_mode_type)

                    if day_schedule:
                        ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                            day_schedule.blocks
                        )
                        self._editing_blocks = [b.to_dict() for b in ui_blocks]

                    break

            return await self.async_step_edit_schedule()

        # Build room list
        room_options = []
        current_room = self.config_entry.data.get(CONF_ROOM_NAME)

        for entry_id, entry_data in self.hass.data[DOMAIN].items():
            if entry_data.get("type") != "room":
                continue

            entry = entry_data.get("entry")
            if not entry:
                continue

            room_name = entry.data.get(CONF_ROOM_NAME)
            if room_name and room_name != current_room:
                room_options.append(
                    selector.SelectOptionDict(value=room_name, label=room_name)
                )

        if not room_options:
            # No other rooms
            return await self.async_step_edit_schedule()

        # Mode type options
        mode_type_options = [
            selector.SelectOptionDict(
                value="normal_weekday", label="Normal - Weekday (Mon-Fri)"
            ),
            selector.SelectOptionDict(
                value="normal_weekend", label="Normal - Weekend (Sat-Sun)"
            ),
            selector.SelectOptionDict(value="homeoffice", label="Homeoffice (daily)"),
        ]

        return self.async_show_form(
            step_id="copy_from_room",
            data_schema=vol.Schema(
                {
                    vol.Required("source_room"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=room_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("source_mode_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=mode_type_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def _save_schedule_and_finish(self) -> FlowResult:
        """Save schedule and finish flow."""
        coordinator = await self._get_room_coordinator()
        if not coordinator:
            return self.async_abort(reason="coordinator_not_found")

        room_name = self.config_entry.data.get(CONF_ROOM_NAME)
        if not room_name:
            return self.async_abort(reason="room_name_missing")

        # Get or create room schedule
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        if not room_schedule:
            room_schedule = RoomSchedule(room_name=room_name)
            coordinator.schedule_engine.update_room_schedule(room_name, room_schedule)

        # Determine which schedule to update
        if self._use_normal_default:
            # Set use_normal flag for this mode
            room_schedule.set_use_normal(self._selected_mode, True)
        else:
            # Convert UI blocks to ScheduleBlocks
            ui_blocks = [ScheduleUIBlock.from_dict(b) for b in self._editing_blocks]
            schedule_blocks = ScheduleStorageManager.ui_blocks_to_schedule_blocks(ui_blocks)
            day_schedule = DaySchedule(blocks=schedule_blocks)

            # Update appropriate schedule
            if self._selected_mode == HUB_MODE_NORMAL:
                if self._selected_schedule_type == SCHEDULE_TYPE_WEEKDAY:
                    room_schedule.normal_weekday = day_schedule
                elif self._selected_schedule_type == SCHEDULE_TYPE_WEEKEND:
                    room_schedule.normal_weekend = day_schedule
            elif self._selected_mode == "homeoffice":
                room_schedule.homeoffice_daily = day_schedule
            else:
                # Custom mode
                room_schedule.set_custom_schedule(self._selected_mode, day_schedule)
                # Clear use_normal flag if it was set
                room_schedule.set_use_normal(self._selected_mode, False)

        # Save to storage
        coordinator.schedule_engine.update_room_schedule(room_name, room_schedule)
        await coordinator.async_save_schedules()

        # Reset state
        self._selected_mode = None
        self._selected_schedule_type = None
        self._editing_blocks = []
        self._use_normal_default = False

        return self.async_create_entry(title="", data={})
