"""Safety monitoring for TaDIY rooms.

Provides three independent safety checks:
1. Overheat protection  — force-off if room temp exceeds a ceiling
2. Frost protection     — force-heat if room temp drops below a floor
3. Valve stuck detection — alert when TRV temp doesn't change despite
   commands being sent (possible mechanical failure)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Thresholds
OVERHEAT_TEMP: float = 28.0  # Force heating off above this
FROST_FLOOR_TEMP: float = 5.0  # Force heating on below this
VALVE_STUCK_TIMEOUT: int = 1800  # 30 min without temp change after command
VALVE_STUCK_MIN_DELTA: float = 0.3  # Expected min change in that period


@dataclass
class SafetyAlert:
    """A safety alert."""

    alert_type: str  # "overheat", "frost", "valve_stuck"
    message: str
    timestamp: datetime = field(default_factory=dt_util.utcnow)
    resolved: bool = False


@dataclass
class SafetyState:
    """Safety state for a room."""

    overheat_active: bool = False
    frost_active: bool = False
    valve_stuck: bool = False
    alerts: list[SafetyAlert] = field(default_factory=list)

    @property
    def any_alert(self) -> bool:
        """Return True if any safety condition is active."""
        return self.overheat_active or self.frost_active or self.valve_stuck


class SafetyManager:
    """Monitors room safety conditions."""

    def __init__(self, room_name: str, debug_callback=None) -> None:
        """Initialize."""
        self.room_name = room_name
        self._debug_fn = debug_callback
        self.state = SafetyState()

        # Valve stuck tracking
        self._last_command_time: datetime | None = None
        self._temp_at_command: float | None = None

    def _debug(self, message: str, *args) -> None:
        """Log debug message."""
        if self._debug_fn:
            self._debug_fn("rooms", message, args)
        else:
            _LOGGER.debug(message, *args)

    def check_overheat(self, current_temp: float | None) -> bool:
        """Check for overheat condition. Returns True if heating must stop."""
        if current_temp is None:
            return False

        was_active = self.state.overheat_active

        if current_temp > OVERHEAT_TEMP:
            if not was_active:
                self._debug(
                    "SAFETY: Overheat detected in %s (%.1f°C > %.1f°C)",
                    self.room_name,
                    current_temp,
                    OVERHEAT_TEMP,
                )
                self.state.alerts.append(
                    SafetyAlert(
                        alert_type="overheat",
                        message=f"Room {self.room_name} overheated at {current_temp}°C",
                    )
                )
            self.state.overheat_active = True
            return True

        # Hysteresis: clear 1°C below threshold
        if was_active and current_temp < OVERHEAT_TEMP - 1.0:
            self._debug(
                "SAFETY: Overheat cleared in %s (%.1f°C)",
                self.room_name,
                current_temp,
            )
            self.state.overheat_active = False

        return False

    def check_frost(self, current_temp: float | None, heating_active: bool) -> bool:
        """Check for frost condition. Returns True if heating must start."""
        if current_temp is None:
            return False

        was_active = self.state.frost_active

        if current_temp < FROST_FLOOR_TEMP:
            if not was_active:
                self._debug(
                    "SAFETY: Frost risk in %s (%.1f°C < %.1f°C)",
                    self.room_name,
                    current_temp,
                    FROST_FLOOR_TEMP,
                )
                self.state.alerts.append(
                    SafetyAlert(
                        alert_type="frost",
                        message=f"Room {self.room_name} frost risk at {current_temp}°C",
                    )
                )
            self.state.frost_active = True
            return True

        # Clear when safely above
        if was_active and current_temp > FROST_FLOOR_TEMP + 1.0:
            self._debug(
                "SAFETY: Frost cleared in %s (%.1f°C)",
                self.room_name,
                current_temp,
            )
            self.state.frost_active = False

        return False

    def on_trv_command_sent(self, current_temp: float | None) -> None:
        """Record that we just sent a command to the TRV."""
        self._last_command_time = dt_util.utcnow()
        self._temp_at_command = current_temp

    def check_valve_stuck(
        self, current_temp: float | None, heating_active: bool
    ) -> bool:
        """Check if valve might be stuck (no temp change after command).

        Only checks when heating is supposed to be active.
        """
        if (
            not heating_active
            or current_temp is None
            or self._last_command_time is None
            or self._temp_at_command is None
        ):
            self.state.valve_stuck = False
            return False

        elapsed = (dt_util.utcnow() - self._last_command_time).total_seconds()
        if elapsed < VALVE_STUCK_TIMEOUT:
            return False  # Too early to judge

        temp_change = abs(current_temp - self._temp_at_command)
        if temp_change < VALVE_STUCK_MIN_DELTA:
            if not self.state.valve_stuck:
                self._debug(
                    "SAFETY: Valve may be stuck in %s "
                    "(temp %.1f->%.1f, delta %.2f in %d min)",
                    self.room_name,
                    self._temp_at_command,
                    current_temp,
                    temp_change,
                    int(elapsed / 60),
                )
                self.state.alerts.append(
                    SafetyAlert(
                        alert_type="valve_stuck",
                        message=f"Room {self.room_name}: valve may be stuck "
                        f"(no temp change in {int(elapsed / 60)} min)",
                    )
                )
            self.state.valve_stuck = True
            return True

        # Temp is changing — valve is working
        self.state.valve_stuck = False
        self._last_command_time = None  # Reset for next check
        return False

    def get_active_alerts(self) -> list[str]:
        """Return list of active alert types."""
        alerts = []
        if self.state.overheat_active:
            alerts.append("overheat")
        if self.state.frost_active:
            alerts.append("frost")
        if self.state.valve_stuck:
            alerts.append("valve_stuck")
        return alerts

    def to_dict(self) -> dict[str, Any]:
        """Serialize state."""
        return {
            "overheat_active": self.state.overheat_active,
            "frost_active": self.state.frost_active,
            "valve_stuck": self.state.valve_stuck,
            "alert_count": len(self.state.alerts),
        }
