"""Schedule engine for TaDIY."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Callable, Any

from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_FROST_PROTECTION_TEMP,
    MODE_MANUAL,
    MODE_OFF,
)
from .schedule_model import RoomSchedule

_LOGGER = logging.getLogger(__name__)


class ScheduleEngine:
    """Engine for calculating target temperatures based on schedules and mode."""

    def __init__(
        self,
        frost_protection_temp: float = DEFAULT_FROST_PROTECTION_TEMP,
        debug_callback: Callable[[str, str, tuple], None] | None = None,
    ):
        """Initialize schedule engine.

        Args:
            frost_protection_temp: Default frost protection temperature
            debug_callback: Optional callback for debug logging (category, message, args)
        """
        self._frost_protection_temp = frost_protection_temp
        self._room_schedules: dict[str, RoomSchedule] = {}
        self._debug_callback = debug_callback

    def _debug(self, message: str, *args: Any) -> None:
        """Log debug message if callback is set."""
        if self._debug_callback:
            self._debug_callback("schedule", message, args)

    def set_debug_callback(
        self, callback: Callable[[str, str, tuple], None] | None
    ) -> None:
        """Set the debug callback."""
        self._debug_callback = callback

    def set_frost_protection_temp(self, temp: float) -> None:
        """Set frost protection temperature."""
        self._frost_protection_temp = temp

    def update_room_schedule(self, room_name: str, schedule: RoomSchedule) -> None:
        """Update schedule for a room."""
        self._room_schedules[room_name] = schedule

    def remove_room_schedule(self, room_name: str) -> None:
        """Remove schedule for a room."""
        if room_name in self._room_schedules:
            del self._room_schedules[room_name]

    def get_target_temperature(
        self,
        room_name: str,
        mode: str,
        dt: datetime | None = None,
    ) -> float | None:
        """
        Get target temperature for room based on current mode and time.

        Args:
            room_name: Name of the room
            mode: Current hub mode (normal|homeoffice|manual|off)
            dt: Datetime to check (defaults to now)

        Returns:
            Target temperature in C, or None if manual mode or no schedule
        """
        if dt is None:
            dt = dt_util.now()

        # Manual mode: Don't provide scheduled temperature
        if mode == MODE_MANUAL:
            self._debug("Manual mode active - no scheduled temperature")
            return None

        # Off mode: Always frost protection
        if mode == MODE_OFF:
            self._debug(
                "Off mode active - using frost protection %.1f",
                self._frost_protection_temp,
            )
            return self._frost_protection_temp

        # Normal or Homeoffice: Use schedules
        room_schedule = self._room_schedules.get(room_name)
        if not room_schedule:
            self._debug("No schedule found for room")
            return None

        is_weekday = dt.weekday() < 5
        current_time = dt.time()

        day_schedule = room_schedule.get_schedule_for_mode(mode, dt)
        schedule_source = mode

        if not day_schedule:
            # Custom mode without own schedule: Fall back to normal schedule
            day_schedule = room_schedule.get_schedule_for_mode("normal", dt)
            schedule_source = "normal (fallback)"
            if not day_schedule:
                self._debug("No schedule for mode %s or normal fallback", mode)
                return None

        target_temp = day_schedule.get_temperature(
            current_time, self._frost_protection_temp
        )

        # Find active block info for logging
        active_block_start = None
        active_block_end = None
        for i, block in enumerate(day_schedule.blocks):
            block_time = block.time
            next_block_time = (
                day_schedule.blocks[i + 1].time
                if i + 1 < len(day_schedule.blocks)
                else None
            )

            if block_time <= current_time:
                if next_block_time is None or current_time < next_block_time:
                    active_block_start = block_time.strftime("%H:%M")
                    active_block_end = (
                        next_block_time.strftime("%H:%M")
                        if next_block_time
                        else "24:00"
                    )
                    break

        self._debug(
            "Active block: %s-%s -> %.1f (%s, %s)",
            active_block_start or "00:00",
            active_block_end or "24:00",
            target_temp,
            schedule_source,
            "weekday" if is_weekday else "weekend",
        )

        return target_temp

    def get_next_schedule_change(
        self,
        room_name: str,
        mode: str,
        dt: datetime | None = None,
    ) -> tuple[datetime, float] | None:
        """
        Get next scheduled temperature change.

        Args:
            room_name: Name of the room
            mode: Current hub mode
            dt: Datetime to check from (defaults to now)

        Returns:
            Tuple of (next_change_datetime, target_temperature) or None
        """
        if dt is None:
            dt = dt_util.now()

        if mode in (MODE_MANUAL, MODE_OFF):
            return None

        room_schedule = self._room_schedules.get(room_name)
        if not room_schedule:
            return None

        day_schedule = room_schedule.get_schedule_for_mode(mode, dt)
        if not day_schedule:
            return None

        current_time = dt.time()
        next_change = day_schedule.get_next_change(current_time)

        if not next_change:
            return None

        next_time, next_temp = next_change

        # Calculate next datetime
        if next_time > current_time:
            # Same day
            next_dt = dt.replace(
                hour=next_time.hour,
                minute=next_time.minute,
                second=0,
                microsecond=0,
            )
        else:
            # Next day
            from datetime import timedelta

            next_dt = dt + timedelta(days=1)
            next_dt = next_dt.replace(
                hour=next_time.hour,
                minute=next_time.minute,
                second=0,
                microsecond=0,
            )

        # Resolve special temps
        if isinstance(next_temp, str):
            next_temp = self._frost_protection_temp

        self._debug(
            "Next change: %s -> %.1f",
            next_dt.strftime("%H:%M"),
            float(next_temp),
        )

        return (next_dt, float(next_temp))

    def is_schedule_active(self, room_name: str, mode: str) -> bool:
        """Check if schedule is active for room in current mode."""
        if mode in (MODE_MANUAL, MODE_OFF):
            return False

        room_schedule = self._room_schedules.get(room_name)
        if not room_schedule:
            return False

        day_schedule = room_schedule.get_schedule_for_mode(mode)
        # Fall back to normal if no custom schedule defined
        if day_schedule is None:
            day_schedule = room_schedule.get_schedule_for_mode("normal")
        return day_schedule is not None and len(day_schedule.blocks) > 0
