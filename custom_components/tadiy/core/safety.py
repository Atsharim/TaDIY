"""Safety monitoring for TaDIY rooms.

Provides four safety checks:
1. Overheat protection  — force-off if room temp exceeds ceiling (28°C)
2. Frost protection     — force-heat if room temp drops below floor (5°C)
3. Valve stuck open     — alert when room continues heating / overheats above target
                          despite heating being inactive (limescale clog / mechanical fault)
4. Heating failure      — alert when room does not warm up despite calling for heat
                          for >= 30 min (boiler outage / pump failure / valve stuck closed)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Thresholds
OVERHEAT_TEMP: float = 28.0  # Force heating off above this (absolute ceiling)
FROST_FLOOR_TEMP: float = 5.0  # Force heating on below this (absolute floor)
OVERHEAT_SETPOINT_DELTA: float = (
    1.5  # °C above setpoint before stuck-open heating detection begins
)
HEATING_FAILURE_SETPOINT_DELTA: float = (
    0.8  # °C below setpoint before stuck-closed / boiler failure detection begins
)
VALVE_STUCK_TIMEOUT: int = 1800  # 30 min evaluation window
VALVE_STUCK_MIN_DELTA: float = (
    0.5  # Expected min climb in that period to declare active runaway heating
)
MIN_TEMP_RISE_ON_HEAT: float = (
    0.0  # Must not be stagnant or falling (temp_rise <= 0.0) when heating
)


@dataclass
class SafetyAlert:
    """A safety alert."""

    alert_type: (
        str  # "valve_stuck_open", "heating_failure", "overheat", "frost", "valve_stuck"
    )
    message: str
    timestamp: datetime = field(default_factory=dt_util.utcnow)
    resolved: bool = False


@dataclass
class SafetyState:
    """Safety state for a room."""

    overheat_active: bool = False
    frost_active: bool = False
    valve_stuck_open: bool = False
    heating_failure: bool = False
    valve_stuck: bool = False  # Legacy compatibility
    alerts: list[SafetyAlert] = field(default_factory=list)

    @property
    def any_alert(self) -> bool:
        """Return True if any safety condition is active."""
        return (
            self.overheat_active
            or self.frost_active
            or self.valve_stuck_open
            or self.heating_failure
            or self.valve_stuck
        )

    @property
    def problem_active(self) -> bool:
        """Return True if an actionable heating problem is active."""
        return self.any_alert

    @property
    def active_problem_type(self) -> str | None:
        """Return identifier of active problem."""
        if self.valve_stuck_open:
            return "valve_stuck_open"
        if self.heating_failure:
            return "heating_failure"
        if self.overheat_active:
            return "overheat"
        if self.frost_active:
            return "frost"
        if self.valve_stuck:
            return "valve_stuck"
        return None

    @property
    def active_problem_description(self) -> str | None:
        """Return human-readable description of active problem."""
        active = [a for a in self.alerts if not a.resolved]
        return active[-1].message if active else None

    @property
    def active_problem_since(self) -> datetime | None:
        """Return timestamp when active problem started."""
        active = [a for a in self.alerts if not a.resolved]
        return active[-1].timestamp if active else None


class SafetyManager:
    """Monitors room safety conditions."""

    def __init__(self, room_name: str, debug_callback=None) -> None:
        """Initialize."""
        self.room_name = room_name
        self._debug_fn = debug_callback
        self.state = SafetyState()

        # Legacy command tracking
        self._last_command_time: datetime | None = None
        self._temp_at_command: float | None = None

        # Heating failure tracking (valve stuck closed / boiler outage / pump failure)
        self._heating_started_at: datetime | None = None
        self._temp_at_heating_start: float | None = None

        # Valve stuck open tracking (limescale clog / room over-heats while idle)
        self._idle_overheat_started_at: datetime | None = None
        self._temp_at_idle_overheat_start: float | None = None

    def _debug(self, message: str, *args) -> None:
        """Log debug message."""
        if self._debug_fn:
            self._debug_fn("rooms", message, args)
        else:
            _LOGGER.debug(message, *args)

    def check_overheat(self, current_temp: float | None) -> bool:
        """Check for absolute overheat condition. Returns True if heating must stop."""
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
                        message=f"Raum {self.room_name} überhitzt ({current_temp:.1f}°C > {OVERHEAT_TEMP:.1f}°C)",
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
            for a in self.state.alerts:
                if a.alert_type == "overheat":
                    a.resolved = True

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
                        message=f"Frostgefahr in Raum {self.room_name} ({current_temp:.1f}°C < {FROST_FLOOR_TEMP:.1f}°C)",
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
            for a in self.state.alerts:
                if a.alert_type == "frost":
                    a.resolved = True

        return False

    def on_trv_command_sent(self, current_temp: float | None) -> None:
        """Record that we just sent a command to the TRV."""
        self._last_command_time = dt_util.utcnow()
        self._temp_at_command = current_temp

    def check_valve_stuck(
        self, current_temp: float | None, heating_active: bool
    ) -> bool:
        """Legacy check for backward compatibility."""
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
            return False

        temp_change = abs(current_temp - self._temp_at_command)
        if temp_change < VALVE_STUCK_MIN_DELTA:
            if not self.state.valve_stuck:
                self.state.alerts.append(
                    SafetyAlert(
                        alert_type="valve_stuck",
                        message=f"Raum {self.room_name}: Ventil reagiert möglicherweise nicht.",
                    )
                )
            self.state.valve_stuck = True
            return True

        self.state.valve_stuck = False
        self._last_command_time = None
        return False

    def check_safety(
        self,
        current_temp: float | None,
        target_temp: float | None,
        heating_active: bool,
        trv_temperatures: list[float] | None = None,
        trv_targets: list[float] | None = None,
        trv_modes: list[str] | None = None,
    ) -> SafetyState:
        """Comprehensive safety and failure monitoring (K-13).

        Detects:
        - Absolute overheat / frost
        - Valve stuck open (limescale clog): Room exceeds target and fails to cool down while idle.
          Cross-checks TRV temperature: if TRVs are cold (<= current_temp + 1.5°C), the warmth
          is due to passive drift from adjacent rooms, NOT a stuck radiator valve.
        - Heating failure (boiler/pump outage or stuck closed): Room fails to rise despite heat call.
          Cross-checks TRV state: if TRVs are off/low (e.g. 5°C), or TRVs are actively hot, false alarms are suppressed.
        """
        if current_temp is None:
            return self.state

        now = dt_util.utcnow()

        # 1. Absolute Overheat & Frost Checks
        self.check_overheat(current_temp)
        self.check_frost(current_temp, heating_active)

        # TRV sensor cross-check
        valid_trvs = [
            t for t in (trv_temperatures or []) if isinstance(t, (int, float))
        ]
        trv_is_hot = True
        trv_actively_heating = False
        if valid_trvs:
            max_trv = max(valid_trvs)
            # A stuck-open radiator must heat its own TRV significantly above room temperature
            trv_is_hot = max_trv > current_temp + 1.5
            # In heating failure check: if TRV is hot, valve and hot water are flowing
            trv_actively_heating = max_trv >= current_temp + 2.5

        # 2. Valve Stuck Open / Uncontrolled Heating (Kalkblockade)
        # Occurs when heating is OFF (or target is lower than room temp) but room temp is significantly above setpoint.
        # Suppressed if TRVs are confirmed cold (passive heating from adjacent rooms).
        if (
            target_temp is not None
            and not heating_active
            and (current_temp >= target_temp + OVERHEAT_SETPOINT_DELTA)
            and trv_is_hot
        ):
            if self._idle_overheat_started_at is None:
                self._idle_overheat_started_at = now
                self._temp_at_idle_overheat_start = current_temp
            else:
                elapsed = (now - self._idle_overheat_started_at).total_seconds()
                if elapsed >= VALVE_STUCK_TIMEOUT:
                    # An open stuck valve actually heats the room up while idle!
                    temp_increase = current_temp - (
                        self._temp_at_idle_overheat_start
                        if self._temp_at_idle_overheat_start is not None
                        else current_temp
                    )
                    if temp_increase >= VALVE_STUCK_MIN_DELTA:
                        if not self.state.valve_stuck_open:
                            msg = (
                                f"Ventil in Raum {self.room_name} klemmt vermutlich offen (Kalkblockade). "
                                f"Raum heizt weiter ({current_temp:.1f}°C bei Soll {target_temp:.1f}°C, Anstieg: +{temp_increase:.2f}°C) "
                                f"trotz inaktiver Heizung seit {int(elapsed / 60)} Min."
                            )
                            self._debug("SAFETY: %s", msg)
                            self.state.alerts.append(
                                SafetyAlert(
                                    alert_type="valve_stuck_open",
                                    message=msg,
                                    timestamp=now,
                                )
                            )
                            self.state.valve_stuck_open = True
        else:
            if self.state.valve_stuck_open:
                self._debug(
                    "SAFETY: Valve stuck open cleared in %s (%.1f°C)",
                    self.room_name,
                    current_temp,
                )
                self.state.valve_stuck_open = False
                for a in self.state.alerts:
                    if a.alert_type == "valve_stuck_open":
                        a.resolved = True
            self._idle_overheat_started_at = None
            self._temp_at_idle_overheat_start = None

        # 3. Heating Failure (Kesselausfall / Pumpenausfall / Ventil klemmt geschlossen / TRV reagiert nicht)
        # Occurs when heating is active, room is noticeably below target, and TRVs are NOT hot
        if (
            target_temp is not None
            and heating_active
            and (target_temp - current_temp >= HEATING_FAILURE_SETPOINT_DELTA)
            and not trv_actively_heating
        ):
            if self._heating_started_at is None:
                self._heating_started_at = now
                self._temp_at_heating_start = current_temp
            else:
                elapsed = (now - self._heating_started_at).total_seconds()
                if elapsed >= VALVE_STUCK_TIMEOUT:
                    # Check directional rise
                    temp_rise = current_temp - (
                        self._temp_at_heating_start
                        if self._temp_at_heating_start is not None
                        else current_temp
                    )
                    if temp_rise <= MIN_TEMP_RISE_ON_HEAT:
                        if not self.state.heating_failure:
                            # Diagnose whether TRV failed to follow command or boiler/pipes are cold
                            trv_not_responding = False
                            if trv_targets:
                                valid_targets = [
                                    t
                                    for t in trv_targets
                                    if isinstance(t, (int, float))
                                ]
                                if valid_targets and all(
                                    t <= (current_temp or 20.0) or t <= 10.0
                                    for t in valid_targets
                                ):
                                    trv_not_responding = True
                            if trv_modes and all(m == "off" for m in trv_modes):
                                trv_not_responding = True

                            if trv_not_responding:
                                msg = (
                                    f"Heizungsstörung in Raum {self.room_name}: Thermostat übernimmt Heizbefehl nicht "
                                    f"(steht weiterhin auf 5.0°C bzw. Aus trotz Heizanforderung seit {int(elapsed / 60)} Min). "
                                    f"Möglicher Funkabriss, leere Batterie oder blockierter Stellmotor."
                                )
                            else:
                                msg = (
                                    f"Heizungsstörung in Raum {self.room_name}: Keine Erwärmung seit {int(elapsed / 60)} Min "
                                    f"trotz Heizanforderung (Ist: {current_temp:.1f}°C, Soll: {target_temp:.1f}°C, Anstieg: {temp_rise:+.2f}°C). "
                                    f"Möglicher Kessel-/Pumpenausfall oder Ventil klemmt geschlossen."
                                )
                            self._debug("SAFETY: %s", msg)
                            self.state.alerts.append(
                                SafetyAlert(
                                    alert_type="heating_failure",
                                    message=msg,
                                    timestamp=now,
                                )
                            )
                            self.state.heating_failure = True
        else:
            if self.state.heating_failure:
                self._debug(
                    "SAFETY: Heating failure cleared in %s (%.1f°C)",
                    self.room_name,
                    current_temp,
                )
                self.state.heating_failure = False
                for a in self.state.alerts:
                    if a.alert_type == "heating_failure":
                        a.resolved = True
            self._heating_started_at = None
            self._temp_at_heating_start = None

        return self.state

    def get_active_alerts(self) -> list[str]:
        """Return list of active alert types."""
        alerts = []
        if self.state.overheat_active:
            alerts.append("overheat")
        if self.state.frost_active:
            alerts.append("frost")
        if self.state.valve_stuck_open:
            alerts.append("valve_stuck_open")
        if self.state.heating_failure:
            alerts.append("heating_failure")
        if self.state.valve_stuck:
            alerts.append("valve_stuck")
        return alerts

    def to_dict(self) -> dict[str, Any]:
        """Serialize state."""
        return {
            "overheat_active": self.state.overheat_active,
            "frost_active": self.state.frost_active,
            "valve_stuck_open": self.state.valve_stuck_open,
            "heating_failure": self.state.heating_failure,
            "valve_stuck": self.state.valve_stuck,
            "problem_active": self.state.any_alert,
            "problem_type": self.state.active_problem_type,
            "problem_description": self.state.active_problem_description,
            "problem_since": (
                self.state.active_problem_since.isoformat()
                if self.state.active_problem_since
                else None
            ),
            "alert_count": len([a for a in self.state.alerts if not a.resolved]),
        }
