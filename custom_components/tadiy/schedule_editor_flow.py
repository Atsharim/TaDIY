"""Schedule editor flow steps for TaDIY options flow."""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

import voluptuous as vol

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ROOM_NAME,
    DEFAULT_HUB_MODES,
    DOMAIN,
    HUB_MODE_NORMAL,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    MODE_MANUAL,
    MODE_OFF,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKDAY,
    SCHEDULE_TYPE_WEEKEND,
)
from .core.schedule_model import DaySchedule, RoomSchedule, ScheduleBlock
from .schedule_storage import ScheduleStorageManager, ScheduleUIBlock
from .schedule_visualization import (
    generate_blocks_list_html,
    generate_color_legend,
    generate_timeline_html,
)

_LOGGER = logging.getLogger(__name__)


class ScheduleEditorMixin:
    """Mixin for schedule editor functionality in options flow."""

    async def _get_room_coordinator(self):
        """Get coordinator for current room."""
        entry_data = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        return entry_data.get("coordinator") if entry_data else None

    async def _get_hub_coordinator(self):
        """Get hub coordinator."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("is_hub", False):
                entry_data = self.hass.data[DOMAIN].get(entry.entry_id)
                return entry_data.get("coordinator") if entry_data else None
        return None

    async def _load_existing_schedule(self) -> None:
        """Load existing schedule for selected mode/type into editing blocks."""
        coordinator = await self._get_room_coordinator()
        if not coordinator or not coordinator.schedule_engine:
            return

        room_name = self.config_entry.data.get(CONF_ROOM_NAME)
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        if not room_schedule:
            return

        # Determine which schedule to load
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

        # Convert to UI blocks
        if day_schedule and day_schedule.blocks:
            ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                day_schedule.blocks
            )
            self._editing_blocks = [b.to_dict() for b in ui_blocks]

    async def async_step_manage_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage schedules menu."""
        # Get hub coordinator to fetch custom modes
        hub_coordinator = await self._get_hub_coordinator()
        custom_modes = []
        if hub_coordinator:
            custom_modes = hub_coordinator.get_custom_modes()

        # Build mode options
        mode_options = ["normal", "homeoffice"] + custom_modes

        # Filter out modes that don't need schedules
        mode_options = [m for m in mode_options if m not in (MODE_MANUAL, MODE_OFF)]

        return self.async_show_menu(
            step_id="manage_schedules",
            menu_options={mode: mode.capitalize() for mode in mode_options},
        )

    async def async_step_normal(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle normal mode selection."""
        self._selected_mode = "normal"
        return await self.async_step_select_schedule_type(user_input)

    async def async_step_homeoffice(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle homeoffice mode selection."""
        self._selected_mode = "homeoffice"
        self._selected_schedule_type = SCHEDULE_TYPE_DAILY
        return await self.async_step_schedule_options(user_input)

    async def async_step_select_schedule_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select schedule type (weekday/weekend for normal mode)."""
        if user_input is not None:
            self._selected_schedule_type = user_input["schedule_type"]
            return await self.async_step_schedule_options()

        return self.async_show_form(
            step_id="select_schedule_type",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=SCHEDULE_TYPE_WEEKDAY,
                                    label="Werktag (Mo-Fr)",
                                ),
                                selector.SelectOptionDict(
                                    value=SCHEDULE_TYPE_WEEKEND,
                                    label="Wochenende (Sa-So)",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_schedule_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select what to do with the schedule (view/edit/copy)."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "view":
                await self._load_existing_schedule()
                return await self.async_step_edit_schedule()

            elif action == "edit":
                await self._load_existing_schedule()
                # If no existing schedule, create default
                if not self._editing_blocks:
                    default_blocks = ScheduleStorageManager.create_default_schedule(
                        self._selected_schedule_type
                    )
                    self._editing_blocks = [b.to_dict() for b in default_blocks]
                return await self.async_step_edit_schedule()

            elif action == "copy_from_mode":
                return await self.async_step_copy_from_mode()

            elif action == "copy_from_room":
                return await self.async_step_copy_from_room()

            elif action == "use_normal":
                # Set flag to use normal schedule for this mode
                self._use_normal_default = True
                return await self._save_schedule_and_finish()

        # Build menu options
        menu_options = {
            "view": "Zeitplan ansehen",
            "edit": "Zeitplan bearbeiten",
            "copy_from_mode": "Von anderem Modus kopieren",
            "copy_from_room": "Von anderem Raum kopieren",
        }

        # Add "use normal" option for custom modes
        if self._selected_mode not in ("normal", "homeoffice"):
            menu_options["use_normal"] = "Normal-Zeitplan als Standard verwenden"

        return self.async_show_menu(
            step_id="schedule_options",
            menu_options=menu_options,
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit schedule with timeline visualization."""
        errors: dict[str, str] = {}

        if user_input is not None:
            action = user_input.get("action")

            if action == "save":
                # Validate before saving
                ui_blocks = [
                    ScheduleUIBlock.from_dict(b) for b in self._editing_blocks
                ]
                is_valid, error_msg = ScheduleStorageManager.validate_ui_blocks(
                    ui_blocks
                )

                if is_valid:
                    return await self._save_schedule_and_finish()
                else:
                    errors["base"] = "validation_failed"
                    _LOGGER.warning("Schedule validation failed: %s", error_msg)

            elif action == "add_block":
                return await self.async_step_add_block()

            elif action == "remove_block":
                return await self.async_step_remove_block()

            elif action == "edit_block":
                return await self.async_step_select_block_to_edit()

            elif action == "auto_fix":
                # Auto-fix blocks
                ui_blocks = [
                    ScheduleUIBlock.from_dict(b) for b in self._editing_blocks
                ]
                fixed_blocks = ScheduleStorageManager.auto_fix_ui_blocks(ui_blocks)
                self._editing_blocks = [b.to_dict() for b in fixed_blocks]

                # Validate that auto-fix worked
                is_valid, validation_error = ScheduleStorageManager.validate_ui_blocks(
                    fixed_blocks
                )
                if not is_valid:
                    errors["base"] = "auto_fix_failed"
                    _LOGGER.warning(
                        "Auto-fix failed to create valid schedule: %s", validation_error
                    )

        # Generate visualizations
        display_name = ScheduleStorageManager.get_mode_display_name(
            self._selected_mode, self._selected_schedule_type
        )

        timeline_html = generate_timeline_html(self._editing_blocks)
        blocks_html = generate_blocks_list_html(self._editing_blocks)
        legend_html = generate_color_legend()

        # Combine into description
        description = f"## {display_name}\n\n{timeline_html}\n\n{blocks_html}\n\n{legend_html}"

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="save", label="💾 Speichern"),
                                selector.SelectOptionDict(value="add_block", label="➕ Block hinzufügen"),
                                selector.SelectOptionDict(value="edit_block", label="✏️ Block bearbeiten"),
                                selector.SelectOptionDict(value="remove_block", label="🗑️ Block löschen"),
                                selector.SelectOptionDict(value="auto_fix", label="🔧 Auto-Fix (Lücken schließen)"),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"schedule_info": description},
        )

    async def async_step_add_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new schedule block."""
        errors: dict[str, str] = {}

        if user_input is not None:
            start_time = user_input.get("start_time")
            end_time = user_input.get("end_time")
            temp_value = user_input.get("temperature")
            use_off = user_input.get("use_off", False)

            # Normalize end time: Allow user to think in terms of 24:00
            # but store as 23:59 for compatibility
            if end_time == "24:00":
                end_time = "23:59"

            # Determine temperature
            if use_off:
                temperature = "off"
            else:
                try:
                    temperature = float(temp_value)
                    if not (MIN_TARGET_TEMP <= temperature <= MAX_TARGET_TEMP):
                        errors["temperature"] = "temp_out_of_range"
                except (ValueError, TypeError):
                    errors["temperature"] = "invalid_temperature"

            if not errors:
                # Add block
                new_block = ScheduleUIBlock(
                    start_time=start_time,
                    end_time=end_time,
                    temperature=temperature,
                )
                self._editing_blocks.append(new_block.to_dict())
                return await self.async_step_edit_schedule()

        # Determine default start/end times
        default_start = "00:00"
        default_end = "23:59"

        if self._editing_blocks:
            # Suggest next time slot
            sorted_blocks = sorted(self._editing_blocks, key=lambda b: b["end_time"])
            last_end = sorted_blocks[-1]["end_time"]
            if last_end not in ("23:59", "24:00"):
                default_start = last_end

        return self.async_show_form(
            step_id="add_block",
            data_schema=vol.Schema(
                {
                    vol.Required("start_time", default=default_start): selector.TimeSelector(),
                    vol.Required("end_time", default=default_end): selector.TimeSelector(),
                    vol.Optional("temperature", default=20.0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_TARGET_TEMP,
                            max=MAX_TARGET_TEMP,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="°C",
                        )
                    ),
                    vol.Optional("use_off", default=False): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_select_block_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which block to edit."""
        if user_input is not None:
            block_index = int(user_input["block_index"])
            self._editing_block_index = block_index
            return await self.async_step_edit_block()

        # Build block selection options
        sorted_blocks = sorted(
            enumerate(self._editing_blocks), key=lambda x: x[1]["start_time"]
        )

        options = []
        for original_idx, block in sorted_blocks:
            temp = block["temperature"]
            temp_str = f"{temp:.1f}°C" if isinstance(temp, float) else temp.upper()
            label = f"{block['start_time']} - {block['end_time']}: {temp_str}"
            options.append(
                selector.SelectOptionDict(
                    value=str(original_idx),
                    label=label,
                )
            )

        return self.async_show_form(
            step_id="select_block_to_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("block_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing block."""
        if not hasattr(self, "_editing_block_index"):
            return await self.async_step_edit_schedule()

        block_idx = self._editing_block_index
        if block_idx >= len(self._editing_blocks):
            return await self.async_step_edit_schedule()

        block = self._editing_blocks[block_idx]
        errors: dict[str, str] = {}

        if user_input is not None:
            start_time = user_input.get("start_time")
            end_time = user_input.get("end_time")
            temp_value = user_input.get("temperature")
            use_off = user_input.get("use_off", False)

            # Normalize end time: Allow user to think in terms of 24:00
            # but store as 23:59 for compatibility
            if end_time == "24:00":
                end_time = "23:59"

            # Determine temperature
            if use_off:
                temperature = "off"
            else:
                try:
                    temperature = float(temp_value)
                    if not (MIN_TARGET_TEMP <= temperature <= MAX_TARGET_TEMP):
                        errors["temperature"] = "temp_out_of_range"
                except (ValueError, TypeError):
                    errors["temperature"] = "invalid_temperature"

            if not errors:
                # Update block
                self._editing_blocks[block_idx] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "temperature": temperature,
                }
                delattr(self, "_editing_block_index")
                return await self.async_step_edit_schedule()

        # Prepare defaults
        is_off = isinstance(block["temperature"], str)
        temp_default = 20.0 if is_off else float(block["temperature"])

        return self.async_show_form(
            step_id="edit_block",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "start_time", default=block["start_time"]
                    ): selector.TimeSelector(),
                    vol.Required(
                        "end_time", default=block["end_time"]
                    ): selector.TimeSelector(),
                    vol.Optional("temperature", default=temp_default): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_TARGET_TEMP,
                            max=MAX_TARGET_TEMP,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="°C",
                        )
                    ),
                    vol.Optional("use_off", default=is_off): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_block(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a schedule block."""
        if user_input is not None:
            block_index = int(user_input["block_index"])
            if 0 <= block_index < len(self._editing_blocks):
                self._editing_blocks.pop(block_index)
            return await self.async_step_edit_schedule()

        # Build block selection options
        sorted_blocks = sorted(
            enumerate(self._editing_blocks), key=lambda x: x[1]["start_time"]
        )

        options = []
        for original_idx, block in sorted_blocks:
            temp = block["temperature"]
            temp_str = f"{temp:.1f}°C" if isinstance(temp, float) else temp.upper()
            label = f"{block['start_time']} - {block['end_time']}: {temp_str}"
            options.append(
                selector.SelectOptionDict(
                    value=str(original_idx),
                    label=label,
                )
            )

        return self.async_show_form(
            step_id="remove_block",
            data_schema=vol.Schema(
                {
                    vol.Required("block_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_copy_from_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Copy schedule from another mode."""
        if user_input is not None:
            source_mode_type = user_input["source_mode_type"]

            # Load schedule from source
            coordinator = await self._get_room_coordinator()
            room_name = self.config_entry.data.get(CONF_ROOM_NAME)
            room_schedule = (
                coordinator.schedule_engine._room_schedules.get(room_name)
                if coordinator and coordinator.schedule_engine
                else None
            )

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
                day_schedule = room_schedule.get_custom_schedule(source_mode_type)

            if day_schedule and day_schedule.blocks:
                ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                    day_schedule.blocks
                )
                self._editing_blocks = [b.to_dict() for b in ui_blocks]

            return await self.async_step_edit_schedule()

        # Build available modes
        mode_options = []

        coordinator = await self._get_room_coordinator()
        room_name = self.config_entry.data.get(CONF_ROOM_NAME)
        room_schedule = (
            coordinator.schedule_engine._room_schedules.get(room_name)
            if coordinator and coordinator.schedule_engine
            else None
        )

        if room_schedule:
            if room_schedule.normal_weekday:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="normal_weekday",
                        label="Normal - Werktag (Mo-Fr)",
                    )
                )
            if room_schedule.normal_weekend:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="normal_weekend",
                        label="Normal - Wochenende (Sa-So)",
                    )
                )
            if room_schedule.homeoffice_daily:
                mode_options.append(
                    selector.SelectOptionDict(
                        value="homeoffice",
                        label="Homeoffice (täglich)",
                    )
                )
            # Add custom schedules from source room
            if room_schedule.custom_schedules:
                for mode, schedule in room_schedule.custom_schedules.items():
                    display_name = ScheduleStorageManager.get_mode_display_name(mode)
                    mode_options.append(
                        selector.SelectOptionDict(
                            value=mode,
                            label=f"{display_name} (täglich)",
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
                            mode=selector.SelectSelectorMode.LIST,
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
            source_room = user_input["source_room"]
            source_mode_type = user_input["source_mode_type"]

            # Find source room coordinator
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get("is_hub", False):
                    continue

                entry_data = self.hass.data[DOMAIN].get(entry.entry_id)
                if not entry:
                    continue

                if entry.data.get(CONF_ROOM_NAME) == source_room:
                    source_coord = entry_data.get("coordinator")
                    if not source_coord or not source_coord.schedule_engine:
                        continue

                    room_schedule = source_coord.schedule_engine._room_schedules.get(
                        source_room
                    )
                    if not room_schedule:
                        continue

                    # Get appropriate schedule
                    day_schedule = None
                    if source_mode_type == "normal_weekday":
                        day_schedule = room_schedule.normal_weekday
                    elif source_mode_type == "normal_weekend":
                        day_schedule = room_schedule.normal_weekend
                    elif source_mode_type == "homeoffice":
                        day_schedule = room_schedule.homeoffice_daily
                    else:
                        # Custom mode
                        day_schedule = room_schedule.get_custom_schedule(source_mode_type)

                    if day_schedule and day_schedule.blocks:
                        ui_blocks = ScheduleStorageManager.schedule_blocks_to_ui_blocks(
                            day_schedule.blocks
                        )
                        self._editing_blocks = [b.to_dict() for b in ui_blocks]
                    break

            return await self.async_step_edit_schedule()

        # Build room list
        room_options = []
        current_room = self.config_entry.data.get(CONF_ROOM_NAME)

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("is_hub", False):
                continue

            room_name = entry.data.get(CONF_ROOM_NAME)
            if room_name and room_name != current_room:
                room_options.append(
                    selector.SelectOptionDict(
                        value=room_name,
                        label=room_name,
                    )
                )

        if not room_options:
            # No other rooms
            return await self.async_step_edit_schedule()

        # Build mode type options
        mode_type_options = [
            selector.SelectOptionDict(
                value="normal_weekday",
                label="Normal - Werktag",
            ),
            selector.SelectOptionDict(
                value="normal_weekend",
                label="Normal - Wochenende",
            ),
            selector.SelectOptionDict(
                value="homeoffice",
                label="Homeoffice",
            ),
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
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def _save_schedule_and_finish(self) -> FlowResult:
        """Save the schedule and finish the flow."""
        coordinator = await self._get_room_coordinator()
        if not coordinator or not coordinator.schedule_engine:
            return self.async_abort(reason="coordinator_not_found")

        room_name = self.config_entry.data.get(CONF_ROOM_NAME)

        # Get or create room schedule
        room_schedule = coordinator.schedule_engine._room_schedules.get(room_name)
        if not room_schedule:
            room_schedule = RoomSchedule(room_name=room_name)
            coordinator.schedule_engine.update_room_schedule(room_name, room_schedule)

        # Determine which schedule to update
        if self._use_normal_default:
            # Set flag to use normal schedule
            room_schedule.set_use_normal(self._selected_mode, True)
            _LOGGER.info(
                "Mode %s set to use normal schedule as default", self._selected_mode
            )
        else:
            # Clear use_normal flag if it was set
            room_schedule.set_use_normal(self._selected_mode, False)

            # Convert UI blocks to schedule blocks
            ui_blocks = [ScheduleUIBlock.from_dict(b) for b in self._editing_blocks]
            schedule_blocks = ScheduleStorageManager.ui_blocks_to_schedule_blocks(
                ui_blocks
            )

            # Create day schedule
            if self._selected_schedule_type == SCHEDULE_TYPE_WEEKDAY:
                day_schedule = DaySchedule(
                    schedule_type=SCHEDULE_TYPE_WEEKDAY, blocks=schedule_blocks
                )
                room_schedule.normal_weekday = day_schedule
            elif self._selected_schedule_type == SCHEDULE_TYPE_WEEKEND:
                day_schedule = DaySchedule(
                    schedule_type=SCHEDULE_TYPE_WEEKEND, blocks=schedule_blocks
                )
                room_schedule.normal_weekend = day_schedule
            elif self._selected_schedule_type == SCHEDULE_TYPE_DAILY:
                day_schedule = DaySchedule(
                    schedule_type=SCHEDULE_TYPE_DAILY, blocks=schedule_blocks
                )
                # Map to appropriate mode
                if self._selected_mode == "homeoffice":
                    room_schedule.homeoffice_daily = day_schedule
                else:
                    # Custom mode - use new custom_schedules dict
                    room_schedule.set_custom_schedule(self._selected_mode, day_schedule)

        # Update in coordinator
        coordinator.schedule_engine.update_room_schedule(room_name, room_schedule)

        # Save to storage
        await coordinator.async_save_schedules()

        _LOGGER.info(
            "Saved schedule for room=%s, mode=%s, type=%s, use_normal=%s",
            room_name,
            self._selected_mode,
            self._selected_schedule_type,
            self._use_normal_default,
        )

        # Reset state
        self._selected_mode = None
        self._selected_schedule_type = None
        self._editing_blocks = []
        self._use_normal_default = False

        return self.async_create_entry(title="", data={})
