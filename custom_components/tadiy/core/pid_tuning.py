"""PID auto-tuning using Ziegler-Nichols method for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Auto-tuning constants
MIN_OSCILLATION_PERIOD = timedelta(minutes=10)  # Minimum valid oscillation period
MAX_OSCILLATION_PERIOD = timedelta(hours=4)  # Maximum valid oscillation period
MIN_AMPLITUDE = 0.2  # Minimum temperature amplitude (°C)
REQUIRED_CYCLES = 2  # Number of oscillation cycles to measure


@dataclass
class OscillationMeasurement:
    """Measurement of a single temperature oscillation."""

    peak_time: datetime
    peak_temp: float
    valley_time: datetime
    valley_temp: float

    @property
    def amplitude(self) -> float:
        """Get oscillation amplitude."""
        return abs(self.peak_temp - self.valley_temp)

    @property
    def period(self) -> timedelta:
        """Get oscillation period (peak to peak or valley to valley)."""
        return abs(self.valley_time - self.peak_time) * 2

    @property
    def is_valid(self) -> bool:
        """Check if measurement is valid."""
        if self.amplitude < MIN_AMPLITUDE:
            return False
        if not MIN_OSCILLATION_PERIOD <= self.period <= MAX_OSCILLATION_PERIOD:
            return False
        return True


@dataclass
class PIDTuningState:
    """State tracking for PID auto-tuning process."""

    room_name: str
    tuning_active: bool = False
    started_at: datetime | None = None

    # Oscillation tracking
    oscillations: list[OscillationMeasurement] = None
    last_peak_temp: float | None = None
    last_peak_time: datetime | None = None
    last_valley_temp: float | None = None
    last_valley_time: datetime | None = None

    # Current state tracking
    current_direction: str | None = None  # "rising" or "falling"
    last_temp: float | None = None
    last_update: datetime | None = None

    # Ultimate gain method (Ziegler-Nichols relay)
    ultimate_gain: float | None = None  # Ku
    ultimate_period: float | None = None  # Tu (in seconds)

    # Calculated PID parameters
    tuned_kp: float | None = None
    tuned_ki: float | None = None
    tuned_kd: float | None = None
    tuning_complete: bool = False

    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.oscillations is None:
            self.oscillations = []

    def start_tuning(self) -> None:
        """Start auto-tuning process."""
        self.tuning_active = True
        self.started_at = dt_util.utcnow()
        self.oscillations = []
        self.last_peak_temp = None
        self.last_peak_time = None
        self.last_valley_temp = None
        self.last_valley_time = None
        self.current_direction = None
        self.last_temp = None
        self.last_update = None
        self.ultimate_gain = None
        self.ultimate_period = None
        self.tuned_kp = None
        self.tuned_ki = None
        self.tuned_kd = None
        self.tuning_complete = False
        _LOGGER.info("Room %s: Started PID auto-tuning", self.room_name)

    def stop_tuning(self) -> None:
        """Stop auto-tuning process."""
        self.tuning_active = False
        _LOGGER.info(
            "Room %s: Stopped PID auto-tuning (collected %d oscillations)",
            self.room_name,
            len(self.oscillations),
        )

    def update_with_temperature(self, current_temp: float) -> bool:
        """
        Update tuning state with new temperature measurement.

        Args:
            current_temp: Current room temperature

        Returns:
            True if tuning is complete, False otherwise
        """
        if not self.tuning_active or self.tuning_complete:
            return False

        now = dt_util.utcnow()

        # Initialize tracking on first measurement
        if self.last_temp is None:
            self.last_temp = current_temp
            self.last_update = now
            return False

        # Detect direction change (peak or valley)
        temp_change = current_temp - self.last_temp

        # Determine current direction
        if abs(temp_change) > 0.01:  # Ignore noise
            if temp_change > 0:
                new_direction = "rising"
            else:
                new_direction = "falling"

            # Detect peak (was rising, now falling)
            if self.current_direction == "rising" and new_direction == "falling":
                if self.last_peak_temp is None or self.last_temp > self.last_peak_temp:
                    # Valid peak
                    if self.last_valley_temp is not None and self.last_valley_time is not None:
                        # We have a complete oscillation
                        oscillation = OscillationMeasurement(
                            peak_time=self.last_update,
                            peak_temp=self.last_temp,
                            valley_time=self.last_valley_time,
                            valley_temp=self.last_valley_temp,
                        )

                        if oscillation.is_valid:
                            self.oscillations.append(oscillation)
                            _LOGGER.debug(
                                "Room %s: Detected oscillation #%d (amplitude=%.2f°C, period=%s)",
                                self.room_name,
                                len(self.oscillations),
                                oscillation.amplitude,
                                str(oscillation.period),
                            )

                    self.last_peak_temp = self.last_temp
                    self.last_peak_time = self.last_update

            # Detect valley (was falling, now rising)
            elif self.current_direction == "falling" and new_direction == "rising":
                if self.last_valley_temp is None or self.last_temp < self.last_valley_temp:
                    self.last_valley_temp = self.last_temp
                    self.last_valley_time = self.last_update

            self.current_direction = new_direction

        # Update tracking
        self.last_temp = current_temp
        self.last_update = now

        # Check if we have enough oscillations to calculate PID parameters
        if len(self.oscillations) >= REQUIRED_CYCLES:
            self._calculate_pid_parameters()
            return True

        return False

    def _calculate_pid_parameters(self) -> None:
        """Calculate PID parameters using Ziegler-Nichols method."""
        if len(self.oscillations) < REQUIRED_CYCLES:
            return

        # Calculate average amplitude and period from last oscillations
        recent_oscillations = self.oscillations[-REQUIRED_CYCLES:]
        avg_amplitude = sum(osc.amplitude for osc in recent_oscillations) / len(recent_oscillations)
        avg_period_seconds = sum(osc.period.total_seconds() for osc in recent_oscillations) / len(recent_oscillations)

        # Estimate ultimate gain (Ku) using relay method
        # This is a simplified estimation - in reality would need controlled relay test
        # For now, use a conservative estimate based on amplitude
        self.ultimate_gain = 4.0 / (3.14159 * avg_amplitude)  # Simplified relay formula

        # Ultimate period (Tu)
        self.ultimate_period = avg_period_seconds

        # Ziegler-Nichols PID tuning rules (classic method)
        # Kp = 0.6 * Ku
        # Ki = 2 * Kp / Tu = 1.2 * Ku / Tu
        # Kd = Kp * Tu / 8 = 0.075 * Ku * Tu

        self.tuned_kp = 0.6 * self.ultimate_gain
        self.tuned_ki = 1.2 * self.ultimate_gain / self.ultimate_period
        self.tuned_kd = 0.075 * self.ultimate_gain * self.ultimate_period

        # Apply conservative limits
        self.tuned_kp = max(0.1, min(5.0, self.tuned_kp))
        self.tuned_ki = max(0.001, min(0.1, self.tuned_ki))
        self.tuned_kd = max(0.0, min(1.0, self.tuned_kd))

        self.tuning_complete = True

        _LOGGER.info(
            "Room %s: PID auto-tuning complete - "
            "Ku=%.3f, Tu=%.1fs, Kp=%.3f, Ki=%.4f, Kd=%.3f",
            self.room_name,
            self.ultimate_gain,
            self.ultimate_period,
            self.tuned_kp,
            self.tuned_ki,
            self.tuned_kd,
        )

    def get_tuned_parameters(self) -> tuple[float, float, float] | None:
        """
        Get tuned PID parameters.

        Returns:
            Tuple of (Kp, Ki, Kd) or None if tuning not complete
        """
        if not self.tuning_complete:
            return None
        return (self.tuned_kp, self.tuned_ki, self.tuned_kd)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_name": self.room_name,
            "tuning_active": self.tuning_active,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "tuning_complete": self.tuning_complete,
            "ultimate_gain": self.ultimate_gain,
            "ultimate_period": self.ultimate_period,
            "tuned_kp": self.tuned_kp,
            "tuned_ki": self.tuned_ki,
            "tuned_kd": self.tuned_kd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PIDTuningState:
        """Create from dictionary."""
        return cls(
            room_name=data["room_name"],
            tuning_active=data.get("tuning_active", False),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            tuning_complete=data.get("tuning_complete", False),
            ultimate_gain=data.get("ultimate_gain"),
            ultimate_period=data.get("ultimate_period"),
            tuned_kp=data.get("tuned_kp"),
            tuned_ki=data.get("tuned_ki"),
            tuned_kd=data.get("tuned_kd"),
        )


class PIDAutoTuner:
    """Auto-tuning manager for PID parameters."""

    def __init__(self, room_name: str) -> None:
        """Initialize auto-tuner."""
        self.state = PIDTuningState(room_name=room_name)

    def start_tuning(self) -> None:
        """Start auto-tuning process."""
        self.state.start_tuning()

    def stop_tuning(self) -> None:
        """Stop auto-tuning process."""
        self.state.stop_tuning()

    def is_tuning_active(self) -> bool:
        """Check if tuning is currently active."""
        return self.state.tuning_active and not self.state.tuning_complete

    def update(self, current_temp: float) -> tuple[float, float, float] | None:
        """
        Update tuning with new temperature measurement.

        Args:
            current_temp: Current room temperature

        Returns:
            Tuned PID parameters (Kp, Ki, Kd) if tuning complete, None otherwise
        """
        if self.state.update_with_temperature(current_temp):
            # Tuning complete
            self.state.stop_tuning()
            return self.state.get_tuned_parameters()
        return None

    def get_tuned_parameters(self) -> tuple[float, float, float] | None:
        """Get tuned parameters if available."""
        return self.state.get_tuned_parameters()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return self.state.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PIDAutoTuner:
        """Create from dictionary."""
        tuner = cls(room_name=data["room_name"])
        tuner.state = PIDTuningState.from_dict(data)
        return tuner
