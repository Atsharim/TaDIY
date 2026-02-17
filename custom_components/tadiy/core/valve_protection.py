"""Valve protection for TRV anti-calcification cycling.

Periodically exercises TRV valves to prevent them from seizing due
to calcium build-up or prolonged inactivity.  By default runs once
per week (Sunday 03:00) — opens and closes each valve for a short
cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Default schedule: Sunday 03:00
DEFAULT_CYCLE_DAY: int = 6  # 0=Monday, 6=Sunday
DEFAULT_CYCLE_TIME: time = time(3, 0)

# Cycling parameters
CYCLE_OPEN_TEMP: float = 30.0  # Open valve wide
CYCLE_CLOSE_TEMP: float = 5.0  # Close valve
CYCLE_DURATION_SECONDS: int = 120  # Hold each position for 2 min


@dataclass
class ValveProtectionState:
    """State of valve protection for a room."""

    last_cycle: datetime | None = None
    next_cycle: datetime | None = None
    cycling_active: bool = False
    cycle_phase: str = "idle"  # idle, opening, closing, done
    cycle_started: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "last_cycle": self.last_cycle.isoformat() if self.last_cycle else None,
            "cycling_active": self.cycling_active,
            "cycle_phase": self.cycle_phase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValveProtectionState:
        """Deserialize from dict."""
        last_cycle = None
        if data.get("last_cycle"):
            try:
                last_cycle = datetime.fromisoformat(data["last_cycle"])
            except (ValueError, TypeError):
                pass
        return cls(last_cycle=last_cycle)


class ValveProtectionManager:
    """Manages weekly valve cycling to prevent calcification."""

    def __init__(
        self,
        room_name: str,
        cycle_day: int = DEFAULT_CYCLE_DAY,
        cycle_time: time = DEFAULT_CYCLE_TIME,
        debug_callback=None,
    ) -> None:
        """Initialize."""
        self.room_name = room_name
        self.cycle_day = cycle_day
        self.cycle_time = cycle_time
        self._debug_fn = debug_callback
        self.state = ValveProtectionState()
        self._compute_next_cycle()

    def _debug(self, message: str, *args) -> None:
        """Log debug message."""
        if self._debug_fn:
            self._debug_fn("trv", message, args)
        else:
            _LOGGER.debug(message, *args)

    def _compute_next_cycle(self) -> None:
        """Compute the next scheduled cycle time."""
        now = dt_util.now()
        # Find next occurrence of cycle_day at cycle_time
        days_ahead = self.cycle_day - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and now.time() >= self.cycle_time):
            days_ahead += 7

        from datetime import timedelta

        next_date = now.date() + timedelta(days=days_ahead)
        self.state.next_cycle = dt_util.as_utc(
            datetime.combine(next_date, self.cycle_time, tzinfo=now.tzinfo)
        )

    def should_cycle_now(self) -> bool:
        """Check if it's time to run a valve cycle."""
        if self.state.cycling_active:
            return False  # Already running
        if self.state.next_cycle is None:
            self._compute_next_cycle()
            return False

        now = dt_util.utcnow()
        return now >= self.state.next_cycle

    def start_cycle(self) -> float:
        """Start a valve protection cycle. Returns the temperature to set (open)."""
        self.state.cycling_active = True
        self.state.cycle_phase = "opening"
        self.state.cycle_started = dt_util.utcnow()
        self._debug(
            "Valve protection: Starting cycle for %s (opening to %.0f°C)",
            self.room_name,
            CYCLE_OPEN_TEMP,
        )
        return CYCLE_OPEN_TEMP

    def update_cycle(self) -> tuple[str, float | None]:
        """Update the current cycle phase.

        Returns:
            (phase, target_temp): Current phase and temperature to set
            (None means cycle is done, restore normal target).
        """
        if not self.state.cycling_active or self.state.cycle_started is None:
            return "idle", None

        elapsed = (dt_util.utcnow() - self.state.cycle_started).total_seconds()

        if elapsed < CYCLE_DURATION_SECONDS:
            # Phase 1: Opening
            return "opening", CYCLE_OPEN_TEMP

        if elapsed < CYCLE_DURATION_SECONDS * 2:
            # Phase 2: Closing
            if self.state.cycle_phase != "closing":
                self.state.cycle_phase = "closing"
                self._debug(
                    "Valve protection: Closing valve for %s (%.0f°C)",
                    self.room_name,
                    CYCLE_CLOSE_TEMP,
                )
            return "closing", CYCLE_CLOSE_TEMP

        # Phase 3: Done
        self.state.cycling_active = False
        self.state.cycle_phase = "idle"
        self.state.last_cycle = dt_util.utcnow()
        self._compute_next_cycle()
        self._debug(
            "Valve protection: Cycle complete for %s (next: %s)",
            self.room_name,
            self.state.next_cycle,
        )
        return "done", None

    def to_dict(self) -> dict[str, Any]:
        """Serialize."""
        return self.state.to_dict()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        room_name: str,
        debug_callback=None,
    ) -> ValveProtectionManager:
        """Deserialize."""
        mgr = cls(room_name=room_name, debug_callback=debug_callback)
        mgr.state = ValveProtectionState.from_dict(data)
        mgr._compute_next_cycle()
        return mgr
