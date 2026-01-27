"""Diagnostics and anomaly detection for TaDIY.

Phase 4: Detects hardware failures and anomalous behavior.
- Heating Failure: Valve open but temp falling (Open window / Broken valve)
- Runaway Heat: Valve closed but temp rising (Stuck valve / External heat)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# thresholds
HEATING_FAILURE_THRESHOLD_MINS = 60  # Time to wait before flagging failure
RUNAWAY_HEAT_THRESHOLD_MINS = 60     # Time to wait before flagging runaway
MIN_TEMP_RISE_FOR_HEATING = 0.2      # °C expected rise per hour when heating
MAX_TEMP_RISE_FOR_IDLE = 0.5         # °C max allowed rise per hour when idle
HIGH_VALVE_THRESHOLD = 0.8           # 80% valve opening considered "Trying hard"


@dataclass
class DiagnosticEvent:
    """Represents a detected anomaly."""

    event_type: str  # "heating_failure" or "runaway_heat"
    detected_at: datetime
    message: str
    severity: str = "warning"  # warning, error
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "detected_at": self.detected_at.isoformat(),
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


class DiagnosticsManager:
    """
    Monitors room state over time to detect anomalies.
    """

    def __init__(self, room_name: str) -> None:
        """Initialize diagnostics manager."""
        self.room_name = room_name
        self.active_events: dict[str, DiagnosticEvent] = {}

        # State tracking
        self._last_check: datetime | None = None
        self._heating_start_time: datetime | None = None
        self._start_temp: float | None = None
        self._idle_start_time: datetime | None = None
        self._idle_start_temp: float | None = None

    def update(
        self,
        current_temp: float,
        target_temp: float,
        is_heating: bool,
        valve_position: float | None = None,  # 0.0 - 1.0 or None
    ) -> None:
        """
        Update diagnostics with latest room state.
        Should be called on every coordinator update.
        """
        now = dt_util.utcnow()
        if self._last_check is None:
            self._last_check = now
            self._start_temp = current_temp
            return

        # ---------------------------------------------------------
        # 1. HEATING FAILURE DETECTION
        # ---------------------------------------------------------
        # Logic: If system is "trying hard" (heating active or valve > 80%)
        # but temperature is not rising significantly over time.

        # Define "Trying to heat"
        trying_to_heat = is_heating
        if valve_position is not None and valve_position > HIGH_VALVE_THRESHOLD:
            trying_to_heat = True

        if trying_to_heat:
            if self._heating_start_time is None:
                self._heating_start_time = now
                self._start_temp = current_temp

            # Reset IDLE tracking
            self._idle_start_time = None

            # Check duration
            duration = (now - self._heating_start_time).total_seconds() / 60.0

            if duration >= HEATING_FAILURE_THRESHOLD_MINS:
                # Calculate rise rate (°C per hour)
                total_rise = current_temp - (self._start_temp or current_temp)
                hours = duration / 60.0
                rate = total_rise / hours if hours > 0 else 0

                # Check against expected rise
                # BUT ignore if we are near target (within 0.5°C) - that's just maintenance
                dist_to_target = target_temp - current_temp

                if dist_to_target > 0.5 and rate < MIN_TEMP_RISE_FOR_HEATING:
                    # Anomaly Detected!
                    self._raise_event(
                        "heating_failure",
                        f"Heating active for {int(duration)}m but temp only rose {total_rise:.1f}°C ({rate:.2f}°C/h). Posisble open window or broken valve.",
                        {
                            "duration_mins": int(duration),
                            "temp_rise": round(total_rise, 2),
                            "rate_per_hour": round(rate, 2),
                            "valve_pos": valve_position,
                        }
                    )
                else:
                    # Recovered
                    self._clear_event("heating_failure")

        else:
            # Not heating -> Clear tracking
            self._heating_start_time = None
            self._clear_event("heating_failure")


        # ---------------------------------------------------------
        # 2. RUNAWAY HEAT DETECTION (Stuck Valve)
        # ---------------------------------------------------------
        # Logic: If system is OFF (valve ~0%) but temperature is rising fast.

        # Define "Should be off"
        system_off = not is_heating
        if valve_position is not None and valve_position > 0.1:
             system_off = False # Valve is open, so temp rise is expected

        if system_off:
            if self._idle_start_time is None:
                self._idle_start_time = now
                self._idle_start_temp = current_temp

            # Check duration
            duration = (now - self._idle_start_time).total_seconds() / 60.0

            if duration >= RUNAWAY_HEAT_THRESHOLD_MINS:
                 # Calculate rise
                total_rise = current_temp - (self._idle_start_temp or current_temp)
                hours = duration / 60.0
                rate = total_rise / hours if hours > 0 else 0

                # If rising fast while off
                if rate > MAX_TEMP_RISE_FOR_IDLE:
                     # Anomaly Detected!
                    self._raise_event(
                        "runaway_heat",
                        f"Heating OFF for {int(duration)}m but temp rose {total_rise:.1f}°C ({rate:.2f}°C/h). Possible stuck valve or external heat source.",
                        {
                            "duration_mins": int(duration),
                            "temp_rise": round(total_rise, 2),
                            "rate_per_hour": round(rate, 2),
                        }
                    )
                else:
                     self._clear_event("runaway_heat")
        else:
            self._idle_start_time = None
            self._clear_event("runaway_heat")

        self._last_check = now

    def _raise_event(self, key: str, message: str, details: dict) -> None:
        """Create or update an event."""
        if key not in self.active_events:
            _LOGGER.warning("Room %s Diagnostic Alert: %s", self.room_name, message)
            self.active_events[key] = DiagnosticEvent(
                event_type=key,
                detected_at=dt_util.utcnow(),
                message=message,
                details=details
            )

    def _clear_event(self, key: str) -> None:
        """Remove an event if it exists."""
        if key in self.active_events:
            _LOGGER.info("Room %s Diagnostic Alert Cleared: %s", self.room_name, key)
            del self.active_events[key]

    def get_events(self) -> list[DiagnosticEvent]:
        """Get all active events."""
        return list(self.active_events.values())

    def has_anomaly(self) -> bool:
        """Check if any anomaly is active."""
        return len(self.active_events) > 0
