"""Schedule storage manager for TaDIY with UI support."""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

from .const import (
    HUB_MODE_NORMAL,
    MODE_MANUAL,
    MODE_OFF,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKDAY,
    SCHEDULE_TYPE_WEEKEND,
)
from .core.schedule_model import ScheduleBlock

_LOGGER = logging.getLogger(__name__)


class ScheduleUIBlock:
    """UI representation of a schedule block with explicit start and end times."""

    def __init__(
        self,
        start_time: str,  # HH:MM format
        end_time: str,  # HH:MM format (23:59 for end of day)
        temperature: float | str,  # float or "off"
    ):
        """Initialize UI block."""
        self.start_time = start_time
        self.end_time = end_time
        self.temperature = temperature

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleUIBlock:
        """Create from dictionary."""
        return cls(
            start_time=data["start_time"],
            end_time=data["end_time"],
            temperature=data["temperature"],
        )


class ScheduleStorageManager:
    """Manager for schedule storage with UI support."""

    @staticmethod
    def ui_blocks_to_schedule_blocks(
        ui_blocks: list[ScheduleUIBlock],
    ) -> list[ScheduleBlock]:
        """
        Convert UI blocks (with start+end) to ScheduleBlocks (start only).

        The end_time is validated but not stored - it becomes the start_time
        of the next block.
        """
        if not ui_blocks:
            return []

        schedule_blocks = []
        for ui_block in ui_blocks:
            try:
                # Parse start time
                start_parts = ui_block.start_time.split(":")
                if len(start_parts) != 2:
                    raise ValueError(f"Invalid time format: {ui_block.start_time}")

                hour = int(start_parts[0])
                minute = int(start_parts[1])

                # Validate time range
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"Time out of range: {hour}:{minute}")

                start_time = time(hour, minute)

            except (ValueError, IndexError) as e:
                _LOGGER.error("Invalid time in UI block %s: %s", ui_block.start_time, e)
                raise ValueError(f"Invalid time format: {ui_block.start_time}") from e

            schedule_blocks.append(
                ScheduleBlock(
                    start_time=start_time,
                    temperature=ui_block.temperature,
                )
            )

        return schedule_blocks

    @staticmethod
    def schedule_blocks_to_ui_blocks(
        blocks: list[ScheduleBlock],
    ) -> list[ScheduleUIBlock]:
        """
        Convert ScheduleBlocks to UI blocks by calculating end times.

        End time is derived from the start of the next block,
        or 24:00 for the last block (end of day).
        """
        if not blocks:
            return []

        ui_blocks = []
        for i, block in enumerate(blocks):
            start_time = block.start_time.strftime("%H:%M")

            # Calculate end time
            if i < len(blocks) - 1:
                # End is start of next block
                end_time = blocks[i + 1].start_time.strftime("%H:%M")
            else:
                # Last block ends at 24:00 (end of day)
                end_time = "24:00"

            ui_blocks.append(
                ScheduleUIBlock(
                    start_time=start_time,
                    end_time=end_time,
                    temperature=block.temperature,
                )
            )

        return ui_blocks

    @staticmethod
    def validate_ui_blocks(
        ui_blocks: list[ScheduleUIBlock],
    ) -> tuple[bool, str | None]:
        """
        Validate UI blocks for gaps, overlaps, and 24h coverage.

        Returns:
            (is_valid, error_message)
        """
        if not ui_blocks:
            return False, "At least one block is required"

        # Sort by start time
        sorted_blocks = sorted(ui_blocks, key=lambda b: b.start_time)

        # Validate each individual block
        for block in sorted_blocks:
            # Parse times for comparison
            try:
                start_parts = block.start_time.split(":")
                end_parts = block.end_time.split(":")

                start_h, start_m = int(start_parts[0]), int(start_parts[1])
                end_h, end_m = int(end_parts[0]), int(end_parts[1])

                # Convert to minutes for comparison
                start_minutes = start_h * 60 + start_m
                end_minutes = end_h * 60 + end_m

                # Special case: 23:59 is treated as end of day (1440 minutes)
                if end_h == 23 and end_m == 59:
                    end_minutes = 24 * 60

                if start_minutes >= end_minutes:
                    return False, f"Block {block.start_time}-{block.end_time} has invalid time range"

            except (ValueError, IndexError):
                return False, f"Invalid time format in block {block.start_time}-{block.end_time}"

        # First block must start at 00:00
        if sorted_blocks[0].start_time != "00:00":
            return False, "First block must start at 00:00"

        # Last block must end at 24:00 or 23:59 (end of day)
        last_end = sorted_blocks[-1].end_time
        if last_end != "24:00" and last_end != "23:59":
            return False, "Last block must end at 24:00 or 23:59"

        # Check for gaps and overlaps
        for i in range(len(sorted_blocks) - 1):
            current_end = sorted_blocks[i].end_time
            next_start = sorted_blocks[i + 1].start_time

            if current_end != next_start:
                if current_end < next_start:
                    return (
                        False,
                        f"Gap between {current_end} and {next_start}",
                    )
                else:
                    return (
                        False,
                        f"Overlap between {sorted_blocks[i].start_time} and {next_start}",
                    )

        return True, None

    @staticmethod
    def create_default_schedule(
        schedule_type: str = SCHEDULE_TYPE_WEEKDAY,
    ) -> list[ScheduleUIBlock]:
        """Create a default schedule for initial setup."""
        if schedule_type == SCHEDULE_TYPE_WEEKDAY:
            return [
                ScheduleUIBlock("00:00", "06:00", 18.0),
                ScheduleUIBlock("06:00", "08:00", 21.0),
                ScheduleUIBlock("08:00", "16:00", 18.0),
                ScheduleUIBlock("16:00", "22:00", 21.0),
                ScheduleUIBlock("22:00", "24:00", 18.0),
            ]
        elif schedule_type == SCHEDULE_TYPE_WEEKEND:
            return [
                ScheduleUIBlock("00:00", "08:00", 18.0),
                ScheduleUIBlock("08:00", "23:00", 21.0),
                ScheduleUIBlock("23:00", "24:00", 18.0),
            ]
        else:  # SCHEDULE_TYPE_DAILY
            return [
                ScheduleUIBlock("00:00", "06:00", 18.0),
                ScheduleUIBlock("06:00", "22:00", 21.0),
                ScheduleUIBlock("22:00", "24:00", 18.0),
            ]

    @staticmethod
    def get_mode_schedule_types(mode: str) -> list[str]:
        """
        Get schedule types available for a given mode.

        Returns:
            List of schedule types (weekday/weekend for normal, daily for others)
        """
        if mode == MODE_MANUAL or mode == MODE_OFF:
            return []  # No schedules for these modes

        if mode == HUB_MODE_NORMAL:
            return [SCHEDULE_TYPE_WEEKDAY, SCHEDULE_TYPE_WEEKEND]

        # All other modes (homeoffice, custom modes) use daily schedule
        return [SCHEDULE_TYPE_DAILY]

    @staticmethod
    def mode_requires_schedule(mode: str) -> bool:
        """Check if a mode requires schedule configuration."""
        return mode not in (MODE_MANUAL, MODE_OFF)

    @staticmethod
    def get_mode_display_name(mode: str, schedule_type: str | None = None) -> str:
        """Get display name for mode and schedule type."""
        mode_names = {
            "normal": "Normal",
            "homeoffice": "Homeoffice",
            "manual": "Manual",
            "off": "Off",
        }

        base_name = mode_names.get(mode, mode.capitalize())

        if schedule_type == SCHEDULE_TYPE_WEEKDAY:
            return f"{base_name} - Weekday (Mon-Fri)"
        elif schedule_type == SCHEDULE_TYPE_WEEKEND:
            return f"{base_name} - Weekend (Sat-Sun)"
        elif schedule_type == SCHEDULE_TYPE_DAILY:
            return f"{base_name} (daily)"

        return base_name
