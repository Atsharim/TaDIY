"""Heating control logic for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.util import dt as dt_util

from ..const import DEFAULT_HYSTERESIS

_LOGGER = logging.getLogger(__name__)


class HeatingController:
    """Advanced heating control with hysteresis and deadband."""

    def __init__(self, hysteresis: float = DEFAULT_HYSTERESIS) -> None:
        """Initialize heating controller.

        Args:
            hysteresis: Temperature deadband in °C (default 0.3°C)
        """
        self.hysteresis = hysteresis
        self._heating_active = False

    def should_heat(
        self,
        current_temp: float,
        target_temp: float,
    ) -> tuple[bool, float]:
        """
        Determine if heating should be active with hysteresis.

        Hysteresis prevents rapid on/off cycling by creating a deadband:
        - When heating is OFF: Turn ON if temp < (target - hysteresis/2)
        - When heating is ON: Turn OFF if temp >= (target + hysteresis/2)

        Example with target=21°C, hysteresis=0.3°C:
        - Heating turns ON at 20.85°C
        - Heating turns OFF at 21.15°C

        Args:
            current_temp: Current room temperature in °C
            target_temp: Target temperature in °C

        Returns:
            (should_heat, effective_target) tuple
        """
        if self._heating_active:
            # Heating is ON, turn off if we exceed target + hysteresis/2
            turn_off_threshold = target_temp + (self.hysteresis / 2)
            if current_temp >= turn_off_threshold:
                self._heating_active = False
                _LOGGER.debug(
                    "Hysteresis: Heating OFF (current=%.2f°C >= threshold=%.2f°C)",
                    current_temp,
                    turn_off_threshold,
                )
        else:
            # Heating is OFF, turn on if we fall below target - hysteresis/2
            turn_on_threshold = target_temp - (self.hysteresis / 2)
            if current_temp < turn_on_threshold:
                self._heating_active = True
                _LOGGER.debug(
                    "Hysteresis: Heating ON (current=%.2f°C < threshold=%.2f°C)",
                    current_temp,
                    turn_on_threshold,
                )

        return (self._heating_active, target_temp)

    def set_hysteresis(self, hysteresis: float) -> None:
        """Update hysteresis value."""
        self.hysteresis = hysteresis
        _LOGGER.debug("Hysteresis updated to %.2f°C", hysteresis)


    def reset(self) -> None:
        """Reset controller state (call when mode changes)."""
        self._heating_active = False
        _LOGGER.debug("Hysteresis: Controller reset")


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
        """Initialize PID heating controller.

        Args:
            pid_config: PID configuration (uses defaults if None)
            hysteresis: Temperature deadband in °C
        """
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
        """
        Calculate PID controller output.

        PID control provides smoother temperature regulation:
        - P (Proportional): Reacts to current error
        - I (Integral): Eliminates steady-state offset
        - D (Derivative): Dampens oscillations

        Args:
            current_temp: Current room temperature in °C
            target_temp: Target temperature in °C
            dt: Time delta (calculated if None)

        Returns:
            Temperature adjustment in °C (-10.0 to +10.0)
        """
        now = dt_util.utcnow()
        if self._last_update is None:
            self._last_update = now
            dt_seconds = 1.0
        else:
            dt_seconds = (now - self._last_update).total_seconds()
            self._last_update = now

        # Calculate error
        error = target_temp - current_temp

        # Proportional term
        p_term = self.config.kp * error

        # Integral term (with anti-windup)
        self._integral += error * dt_seconds
        self._integral = max(
            -self.config.integral_max,
            min(self.config.integral_max, self._integral),
        )
        i_term = self.config.ki * self._integral

        # Derivative term
        d_error = (error - self._last_error) / dt_seconds if dt_seconds > 0 else 0
        d_term = self.config.kd * d_error
        self._last_error = error

        # PID output
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
        """Reset PID state (call when mode changes or after long pause)."""
        super().reset()
        self._integral = 0.0
        self._last_error = 0.0
        self._last_update = None
        _LOGGER.debug("PID: Controller reset")
