"""Heating control logic for TaDIY.

Provides hysteresis-based on/off control with minimum cycle time
protection and trend-aware state transitions to prevent erratic
TRV switching caused by sensor noise.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.util import dt as dt_util

from ..const import DEFAULT_HYSTERESIS

_LOGGER = logging.getLogger(__name__)

# Minimum time between heating state changes (on->off or off->on).
# 5 minutes prevents rapid cycling and gives TRVs time to settle.
MIN_CYCLE_SECONDS: int = 300

# Number of recent temperature readings to keep for trend detection.
TREND_WINDOW_SIZE: int = 6

# Minimum temperature delta (°C) between readings to consider meaningful.
# Readings within this band are treated as noise and ignored for decisions.
NOISE_FLOOR: float = 0.05

# Trend threshold (°C per reading) below which trend is considered flat.
TREND_DEAD_ZONE: float = 0.03


class HeatingController:
    """Heating control with hysteresis, trend awareness, and cycle protection.

    The controller uses four layers of stability:
    1. Hysteresis deadband: prevents toggling around the target.
    2. Trend guard: suppresses state flips when temperature is moving
       in a direction that makes the flip unnecessary — applied globally,
       not just inside the deadband.
    3. Minimum cycle time: hard limit on state change frequency.
    4. Consecutive confirmation: requires multiple readings in agreement
       before allowing a state change, filtering single-sample spikes.
    """

    def __init__(self, hysteresis: float = DEFAULT_HYSTERESIS) -> None:
        self.hysteresis = hysteresis
        self._heating_active = False
        self._last_state_change: datetime | None = None
        self._temp_history: deque[tuple[float, datetime]] = deque(
            maxlen=TREND_WINDOW_SIZE
        )
        # Consecutive readings that agree on a state change before we flip.
        self._flip_confirm_count: int = 0
        self._flip_confirm_target: int = 2

    def should_heat(
        self,
        current_temp: float,
        target_temp: float,
    ) -> tuple[bool, float]:
        """Determine if heating should be active.

        Hysteresis thresholds:
        - OFF -> ON:  current_temp < target - hysteresis/2
        - ON  -> OFF: current_temp >= target + hysteresis/2

        Trend guard (applied globally):
        - Suppresses OFF if temperature is rising toward target.
        - Suppresses ON if temperature is falling away from target.

        Consecutive confirmation:
        - A state change requires 2 consecutive readings that agree.

        Returns:
            (should_heat, effective_target) tuple.
        """
        now = dt_util.utcnow()
        self._temp_history.append((current_temp, now))

        turn_on_threshold = target_temp - (self.hysteresis / 2)
        turn_off_threshold = target_temp + (self.hysteresis / 2)

        # --- Raw hysteresis decision ---
        desired = self._heating_active
        if self._heating_active:
            if current_temp >= turn_off_threshold:
                desired = False
        else:
            if current_temp < turn_on_threshold:
                desired = True

        # --- Trend guard (global, not just in deadband) ---
        if desired != self._heating_active and len(self._temp_history) >= 3:
            trend = self._get_trend()

            if abs(trend) > TREND_DEAD_ZONE:
                if self._heating_active and not desired and trend > TREND_DEAD_ZONE:
                    # Temp still rising → don't turn off yet
                    _LOGGER.debug(
                        "Trend guard: suppressing OFF (trend=+%.3f°C/reading)",
                        trend,
                    )
                    desired = True
                    self._flip_confirm_count = 0
                elif not self._heating_active and desired and trend < -TREND_DEAD_ZONE:
                    # Temp still falling → don't turn on yet
                    _LOGGER.debug(
                        "Trend guard: suppressing ON (trend=%.3f°C/reading)",
                        trend,
                    )
                    desired = False
                    self._flip_confirm_count = 0

        # --- Consecutive confirmation gate ---
        if desired != self._heating_active:
            self._flip_confirm_count += 1
            if self._flip_confirm_count < self._flip_confirm_target:
                _LOGGER.debug(
                    "Confirm gate: %s->%s needs %d/%d confirmations",
                    "ON" if self._heating_active else "OFF",
                    "ON" if desired else "OFF",
                    self._flip_confirm_count,
                    self._flip_confirm_target,
                )
                return (self._heating_active, target_temp)
        else:
            # Readings agree with current state — reset counter
            self._flip_confirm_count = 0

        # --- Enforce minimum cycle time ---
        if desired != self._heating_active:
            if self._last_state_change is not None:
                elapsed = (now - self._last_state_change).total_seconds()
                if elapsed < MIN_CYCLE_SECONDS:
                    _LOGGER.debug(
                        "Cycle guard: suppressed %s->%s (%.0fs < %ds)",
                        "ON" if self._heating_active else "OFF",
                        "ON" if desired else "OFF",
                        elapsed,
                        MIN_CYCLE_SECONDS,
                    )
                    return (self._heating_active, target_temp)

            self._heating_active = desired
            self._last_state_change = now
            self._flip_confirm_count = 0
            _LOGGER.debug(
                "Heating %s (current=%.2f°C, target=%.2f°C, band=[%.2f, %.2f])",
                "ON" if desired else "OFF",
                current_temp,
                target_temp,
                turn_on_threshold,
                turn_off_threshold,
            )

        return (self._heating_active, target_temp)

    def _get_trend(self) -> float:
        """Calculate temperature trend using time-weighted linear regression.

        Returns trend in °C per reading interval. Positive = rising.
        Uses timestamps for accuracy instead of assuming equal intervals.
        """
        if len(self._temp_history) < 2:
            return 0.0

        temps = [t for t, _ in self._temp_history]
        times = [ts for _, ts in self._temp_history]

        # Use elapsed seconds from first reading as x-axis
        t0 = times[0]
        x = [(t - t0).total_seconds() for t in times]

        if x[-1] - x[0] < 1.0:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(temps)
        sum_xy = sum(xi * yi for xi, yi in zip(x, temps))
        sum_x2 = sum(xi * xi for xi in x)

        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < 1e-10:
            return 0.0

        # Slope in °C/second
        slope = (n * sum_xy - sum_x * sum_y) / denom

        # Convert to °C per average reading interval
        avg_interval = (x[-1] - x[0]) / (n - 1) if n > 1 else 30.0
        trend_per_reading = slope * avg_interval

        return trend_per_reading

    def set_hysteresis(self, hysteresis: float) -> None:
        """Update hysteresis value."""
        self.hysteresis = hysteresis
        _LOGGER.debug("Hysteresis updated to %.2f°C", hysteresis)

    def reset(self) -> None:
        """Reset controller state (call when mode changes)."""
        self._heating_active = False
        self._last_state_change = None
        self._temp_history.clear()
        self._flip_confirm_count = 0
        _LOGGER.debug("Controller reset")


@dataclass
class PIDConfig:
    """PID controller configuration."""

    kp: float = 0.5  # Proportional gain
    ki: float = 0.01  # Integral gain
    kd: float = 0.1  # Derivative gain
    integral_max: float = 10.0  # Anti-windup limit


class PIDHeatingController(HeatingController):
    """PID-based heating controller with hysteresis."""

    def __init__(
        self,
        pid_config: PIDConfig | None = None,
        hysteresis: float = DEFAULT_HYSTERESIS,
    ) -> None:
        super().__init__(hysteresis)
        self.config = pid_config or PIDConfig()
        self._integral = 0.0
        self._last_error = 0.0
        self._last_update = None

    def calculate_output(
        self,
        current_temp: float,
        target_temp: float,
        dt: timedelta | None = None,
    ) -> float:
        """Calculate PID controller output.

        Returns:
            Temperature adjustment in °C (-10.0 to +10.0).
        """
        now = dt_util.utcnow()
        if self._last_update is None:
            self._last_update = now
            dt_seconds = 1.0
        else:
            dt_seconds = (now - self._last_update).total_seconds()
            self._last_update = now

        error = target_temp - current_temp

        # Proportional
        p_term = self.config.kp * error

        # Integral (with anti-windup)
        self._integral += error * dt_seconds
        self._integral = max(
            -self.config.integral_max,
            min(self.config.integral_max, self._integral),
        )
        i_term = self.config.ki * self._integral

        # Derivative
        d_error = (error - self._last_error) / dt_seconds if dt_seconds > 0 else 0
        d_term = self.config.kd * d_error
        self._last_error = error

        output = p_term + i_term + d_term

        _LOGGER.debug(
            "PID: error=%.2f°C, P=%.2f, I=%.2f, D=%.2f, output=%.2f",
            error,
            p_term,
            i_term,
            d_term,
            output,
        )

        return output

    def reset(self) -> None:
        """Reset PID and hysteresis state."""
        super().reset()
        self._integral = 0.0
        self._last_error = 0.0
        self._last_update = None
