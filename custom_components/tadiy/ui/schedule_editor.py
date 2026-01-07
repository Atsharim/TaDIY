"""Schedule editor UI helper for TaDIY."""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from ..const import (
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    SCHEDULE_TEMP_FROST,
    SCHEDULE_TEMP_OFF,
)
from ..models.schedule import DaySchedule, ScheduleBlock

_LOGGER = logging.getLogger(__name__)


class ScheduleEditor:
    """Helper class for schedule editing in options flow."""

    @staticmethod
    def render_timeline(blocks: list[dict[str, Any]]) -> str:
        """
        Render ASCII timeline visualization.
        
        Args:
            blocks: List of dicts with 'start', 'end', 'temp'
        
        Returns:
            Multi-line ASCII art timeline
        """
        if not blocks:
            return "║  (No schedule defined)  ║"

        # Build timeline string
        timeline = "╔" + "═" * 58 + "╗\n"
        timeline += "║ 00:00 "

        for block in blocks:
            start = block["start"]
            end = block["end"]
            temp = block["temp"]

            # Calculate block width (rough approximation)
            start_hour = int(start.split(":")[0])
            end_hour = int(end.split(":")[0])
            width = max(1, (end_hour - start_hour) * 2)

            # Temperature display
            if temp == SCHEDULE_TEMP_FROST:
                temp_str = "FROST"
                char = "▓"
            elif temp == SCHEDULE_TEMP_OFF:
                temp_str = "OFF"
                char = "░"
            else:
                temp_str = f"{temp}°C"
                char = "█"

            # Draw block
            timeline += char * width
            timeline += f" {end} "

        timeline += "║\n"
        
        # Temperature labels
        timeline += "║ "
        for block in blocks:
            temp = block["temp"]
            if temp == SCHEDULE_TEMP_FROST:
                temp_str = "FROST"
            elif temp == SCHEDULE_TEMP_OFF:
                temp_str = "OFF"
            else:
                temp_str = f"{temp}°C"
            
            timeline += f"{temp_str:<8} "
        
        timeline += "║\n"
        timeline += "╚" + "═" * 58 + "╝"

        return timeline

    @staticmethod
    def validate_blocks(blocks: list[dict[str, Any]]) -> list[str]:
        """
        Validate schedule blocks for gaps and overlaps.
        
        Args:
            blocks: List of block dicts
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not blocks:
            return errors

        # Sort by start time
        sorted_blocks = sorted(blocks, key=lambda b: b["start"])

        # Must start at 00:00
        if sorted_blocks[0]["start"] != "00:00":
            errors.append("First block must start at 00:00")

        # Check for gaps
        for i in range(len(sorted_blocks) - 1):
            current_end = sorted_blocks[i]["end"]
            next_start = sorted_blocks[i + 1]["start"]

            if current_end != next_start:
                errors.append(
                    f"Gap detected between {current_end} and {next_start}. "
                    "Blocks must be continuous."
                )

        # Last block must end at 24:00
        if sorted_blocks[-1]["end"] != "24:00":
            errors.append("Last block must end at 24:00")

        # Validate temperature values
        for i, block in enumerate(sorted_blocks):
            temp = block["temp"]
            if isinstance(temp, str):
                if temp not in (SCHEDULE_TEMP_FROST, SCHEDULE_TEMP_OFF):
                    errors.append(
                        f"Block {i+1}: Invalid temperature '{temp}'. "
                        f"Must be a number or 'frost'/'off'"
                    )
            else:
                try:
                    temp_float = float(temp)
                    if not MIN_TARGET_TEMP <= temp_float <= MAX_TARGET_TEMP:
                        errors.append(
                            f"Block {i+1}: Temperature {temp}°C out of range "
                            f"({MIN_TARGET_TEMP}-{MAX_TARGET_TEMP}°C)"
                        )
                except ValueError:
                    errors.append(f"Block {i+1}: Invalid temperature value")

        return errors

    @staticmethod
    def blocks_to_day_schedule(
        blocks: list[dict[str, Any]], schedule_type: str
    ) -> DaySchedule:
        """
        Convert UI blocks to DaySchedule model.
        
        Args:
            blocks: List of block dicts with 'start', 'end', 'temp'
            schedule_type: weekday/weekend/daily
        
        Returns:
            DaySchedule object
        """
        schedule_blocks = []

        for block in blocks:
            start_str = block["start"]
            temp = block["temp"]

            # Parse time
            hour, minute = map(int, start_str.split(":"))
            start_time = time(hour, minute)

            # Convert temp
            if temp in (SCHEDULE_TEMP_FROST, SCHEDULE_TEMP_OFF):
                temperature = temp
            else:
                temperature = float(temp)

            schedule_blocks.append(
                ScheduleBlock(start_time=start_time, temperature=temperature)
            )

        return DaySchedule(schedule_type=schedule_type, blocks=schedule_blocks)

    @staticmethod
    def day_schedule_to_blocks(day_schedule: DaySchedule | None) -> list[dict[str, Any]]:
        """
        Convert DaySchedule model to UI blocks.
        
        Args:
            day_schedule: DaySchedule object or None
        
        Returns:
            List of block dicts
        """
        if not day_schedule or not day_schedule.blocks:
            # Default empty schedule
            return []

        blocks = []
        sorted_blocks = sorted(day_schedule.blocks, key=lambda b: b.start_time)

        for i, block in enumerate(sorted_blocks):
            # Calculate end time (start of next block or 24:00)
            if i < len(sorted_blocks) - 1:
                end_time = sorted_blocks[i + 1].start_time
            else:
                end_time = time(0, 0)  # Represents 24:00

            blocks.append({
                "start": block.start_time.strftime("%H:%M"),
                "end": "24:00" if end_time == time(0, 0) else end_time.strftime("%H:%M"),
                "temp": block.temperature,
            })

        return blocks

    @staticmethod
    def get_add_block_schema(existing_blocks: list[dict[str, Any]]) -> vol.Schema:
        """
        Get schema for adding a new block.
        
        Args:
            existing_blocks: Current blocks to calculate defaults
        
        Returns:
            Voluptuous schema
        """
        # Suggest next start time
        if existing_blocks:
            last_block = existing_blocks[-1]
            suggested_start = last_block["end"]
        else:
            suggested_start = "00:00"

        return vol.Schema({
            vol.Required("start_time", default=suggested_start): cv.string,
            vol.Required("end_time", default="24:00"): cv.string,
            vol.Required("temperature", default=20.0): vol.Any(
                vol.Coerce(float),
                vol.In([SCHEDULE_TEMP_FROST, SCHEDULE_TEMP_OFF])
            ),
        })

    @staticmethod
    def parse_time_input(time_str: str) -> str | None:
        """
        Validate and normalize time input.
        
        Args:
            time_str: Time string (HH:MM)
        
        Returns:
            Normalized time string or None if invalid
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return None

            hour = int(parts[0])
            minute = int(parts[1])

            if not (0 <= hour <= 24 and 0 <= minute <= 59):
                return None

            # Special case: 24:00
            if hour == 24 and minute == 0:
                return "24:00"

            return f"{hour:02d}:{minute:02d}"

        except (ValueError, AttributeError):
            return None
