"""Schedule engine for TaDIY."""

from __future__ import annotations

from datetime import datetime
import logging

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

    def __init__(self, frost_protection_temp: float = DEFAULT_FROST_PROTECTION_TEMP):
        """Initialize schedule engine."""
        self._frost_protection_temp = frost_protection_temp
        self._room_schedules: dict[str, RoomSchedule] = {}

    def set_frost_protection_temp(self, temp: float) -> None:
        """Set frost protection temperature."""
        self._frost_protection_temp = temp
        _LOGGER.debug("Frost protection temperature set to %.1f°C", temp)

    def update_room_schedule(self, room_name: str, schedule: RoomSchedule) -> None:
        """Update schedule for a room."""
        self._room_schedules[room_name] = schedule
        _LOGGER.debug("Schedule updated for room: %s", room_name)

    def remove_room_schedule(self, room_name: str) -> None:
        """Remove schedule for a room."""
        if room_name in self._room_schedules:
            del self._room_schedules[room_name]
            _LOGGER.debug("Schedule removed for room: %s", room_name)

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
            Target temperature in °C, or None if manual mode or no schedule
        """
        if dt is None:
            dt = dt_util.now()

        # Manual mode: Don't provide scheduled temperature
        if mode == MODE_MANUAL:
            _LOGGER.debug("Manual mode active, no scheduled temperature for %s", room_name)
            return None

        # Off mode: Always frost protection
        if mode == MODE_OFF:
            _LOGGER.debug(
                "Off mode active, returning frost protection %.1f°C for %s",
                self._frost_protection_temp,
                room_name,
            )
            return self._frost_protection_temp

        # Normal or Homeoffice: Use schedules
        room_schedule = self._room_schedules.get(room_name)
        if not room_schedule:
            _LOGGER.warning("No schedule found for room: %s", room_name)
            return None

        day_schedule = room_schedule.get_schedule_for_mode(mode, dt)
        if not day_schedule:
            _LOGGER.debug(
                "No schedule defined for room %s in mode %s",
                room_name,
                mode,
            )
            return None

        current_time = dt.time()
        target_temp = day_schedule.get_temperature(
            current_time, self._frost_protection_temp
        )

        _LOGGER.debug(
            "Scheduled temperature for %s at %s: %.1f°C (mode: %s)",
            room_name,
            current_time.strftime("%H:%M"),
            target_temp,
            mode,
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

        return (next_dt, float(next_temp))

    def is_schedule_active(self, room_name: str, mode: str) -> bool:
        """Check if schedule is active for room in current mode."""
        if mode in (MODE_MANUAL, MODE_OFF):
            return False

        room_schedule = self._room_schedules.get(room_name)
        if not room_schedule:
            return False

        day_schedule = room_schedule.get_schedule_for_mode(mode)
        return day_schedule is not None and len(day_schedule.blocks) > 0
