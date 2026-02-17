"""Thermal mass learning and cooling rate analysis for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Thermal mass constants
DEFAULT_COOLING_RATE = 0.5  # °C/h (conservative default)
MIN_COOLING_RATE = 0.1  # °C/h
MAX_COOLING_RATE = 3.0  # °C/h
MIN_SAMPLE_DURATION = timedelta(minutes=30)  # Minimum duration for valid sample
COOLING_DAMPENING = 0.15  # 15% weight to new measurement (slower than heating rate)


@dataclass
class CoolingRateSample:
    """Single cooling rate measurement sample."""

    start_time: datetime
    end_time: datetime
    start_temp: float
    end_temp: float
    outdoor_temp: float | None
    cooling_rate: float  # °C/h

    @property
    def duration_hours(self) -> float:
        """Get sample duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600.0

    @property
    def is_valid(self) -> bool:
        """Check if sample is valid for learning."""
        # Must be at least 30 minutes
        if self.end_time - self.start_time < MIN_SAMPLE_DURATION:
            return False
        # Temperature must have decreased
        if self.start_temp <= self.end_temp:
            return False
        # Cooling rate must be within reasonable bounds
        if not MIN_COOLING_RATE <= self.cooling_rate <= MAX_COOLING_RATE:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "start_temp": self.start_temp,
            "end_temp": self.end_temp,
            "outdoor_temp": self.outdoor_temp,
            "cooling_rate": self.cooling_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoolingRateSample:
        """Create from dictionary."""
        return cls(
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            start_temp=data["start_temp"],
            end_temp=data["end_temp"],
            outdoor_temp=data.get("outdoor_temp"),
            cooling_rate=data["cooling_rate"],
        )


@dataclass
class ThermalMassModel:
    """Model for building thermal mass and cooling behavior."""

    room_name: str
    cooling_rate: float = DEFAULT_COOLING_RATE  # °C/h average cooling rate
    cooling_rate_samples: list[CoolingRateSample] = field(default_factory=list)
    sample_count: int = 0
    confidence: float = 0.0  # 0.0-1.0 confidence in learned rate
    last_measurement: datetime | None = None

    # Tracking state for ongoing measurement
    _measurement_start_time: datetime | None = None
    _measurement_start_temp: float | None = None
    _heating_was_active: bool = False

    def start_cooling_measurement(
        self,
        start_temp: float,
        heating_active: bool,
    ) -> None:
        """
        Start tracking a cooling period.

        Args:
            start_temp: Starting temperature
            heating_active: Whether heating is currently active
        """
        now = dt_util.utcnow()

        # Only start measurement when heating stops
        if not heating_active and self._heating_was_active:
            self._measurement_start_time = now
            self._measurement_start_temp = start_temp
            _LOGGER.debug(
                "Room %s: Started cooling measurement at %.2f°C",
                self.room_name,
                start_temp,
            )

        self._heating_was_active = heating_active

    def update_with_cooling_measurement(
        self,
        current_temp: float,
        outdoor_temp: float | None,
    ) -> bool:
        """
        Update cooling rate with new measurement.

        Args:
            current_temp: Current room temperature
            outdoor_temp: Current outdoor temperature

        Returns:
            True if cooling rate was updated, False otherwise
        """
        now = dt_util.utcnow()

        # Check if we have an ongoing measurement
        if self._measurement_start_time is None or self._measurement_start_temp is None:
            return False

        # Calculate duration
        duration = now - self._measurement_start_time
        if duration < MIN_SAMPLE_DURATION:
            return False

        # Calculate temperature drop
        temp_drop = self._measurement_start_temp - current_temp

        # Must have cooled down
        if temp_drop <= 0.05:
            # Temperature hasn't dropped enough, keep measuring
            return False

        # Calculate cooling rate (°C/h)
        duration_hours = duration.total_seconds() / 3600.0
        raw_cooling_rate = temp_drop / duration_hours

        # Create sample
        sample = CoolingRateSample(
            start_time=self._measurement_start_time,
            end_time=now,
            start_temp=self._measurement_start_temp,
            end_temp=current_temp,
            outdoor_temp=outdoor_temp,
            cooling_rate=raw_cooling_rate,
        )

        # Validate sample
        if not sample.is_valid:
            _LOGGER.debug(
                "Room %s: Invalid cooling sample rejected (rate=%.2f°C/h)",
                self.room_name,
                raw_cooling_rate,
            )
            self._reset_measurement()
            return False

        # Apply exponential moving average
        if self.sample_count == 0:
            # First sample
            self.cooling_rate = raw_cooling_rate
        else:
            # Smooth update with dampening
            self.cooling_rate = (
                1 - COOLING_DAMPENING
            ) * self.cooling_rate + COOLING_DAMPENING * raw_cooling_rate

        # Clamp to limits
        self.cooling_rate = max(
            MIN_COOLING_RATE, min(MAX_COOLING_RATE, self.cooling_rate)
        )

        # Update confidence (max at 20 samples)
        self.sample_count += 1
        self.confidence = min(1.0, self.sample_count / 20.0)
        self.last_measurement = now

        # Store sample (keep last 10 samples)
        self.cooling_rate_samples.append(sample)
        if len(self.cooling_rate_samples) > 10:
            self.cooling_rate_samples.pop(0)

        _LOGGER.info(
            "Room %s: Cooling rate updated to %.2f°C/h "
            "(samples=%d, confidence=%.0f%%, raw=%.2f°C/h)",
            self.room_name,
            self.cooling_rate,
            self.sample_count,
            self.confidence * 100,
            raw_cooling_rate,
        )

        self._reset_measurement()
        return True

    def _reset_measurement(self) -> None:
        """Reset ongoing measurement state."""
        self._measurement_start_time = None
        self._measurement_start_temp = None

    def predict_temperature_drop(
        self,
        duration_minutes: int,
        outdoor_temp: float | None = None,
    ) -> float:
        """
        Predict temperature drop over a given duration with no heating.

        Args:
            duration_minutes: Duration in minutes
            outdoor_temp: Optional outdoor temperature for future adjustments

        Returns:
            Predicted temperature drop in °C
        """
        duration_hours = duration_minutes / 60.0
        predicted_drop = self.cooling_rate * duration_hours
        return predicted_drop

    def calculate_required_preheat_time(
        self,
        current_temp: float,
        target_temp: float,
        heating_rate: float,
        no_heating_duration_minutes: int = 0,
    ) -> int:
        """
        Calculate how early to start heating considering thermal mass.

        Args:
            current_temp: Current room temperature
            target_temp: Target temperature
            heating_rate: Known heating rate (°C/h)
            no_heating_duration_minutes: Duration without heating before target time

        Returns:
            Required preheat time in minutes
        """
        # Predict temperature drop during no-heating period
        if no_heating_duration_minutes > 0:
            predicted_drop = self.predict_temperature_drop(no_heating_duration_minutes)
            effective_start_temp = current_temp - predicted_drop
        else:
            effective_start_temp = current_temp

        # Calculate temperature gap
        temp_gap = target_temp - effective_start_temp

        if temp_gap <= 0:
            return 0

        # Calculate heating time needed
        if heating_rate <= 0:
            return 0

        preheat_minutes = int((temp_gap / heating_rate) * 60)

        _LOGGER.debug(
            "Room %s: Preheat calculation - current=%.1f°C, predicted_drop=%.1f°C, "
            "effective_start=%.1f°C, target=%.1f°C, preheat=%d min",
            self.room_name,
            current_temp,
            predicted_drop if no_heating_duration_minutes > 0 else 0.0,
            effective_start_temp,
            target_temp,
            preheat_minutes,
        )

        return preheat_minutes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_name": self.room_name,
            "cooling_rate": self.cooling_rate,
            "sample_count": self.sample_count,
            "confidence": self.confidence,
            "last_measurement": (
                self.last_measurement.isoformat() if self.last_measurement else None
            ),
            "cooling_rate_samples": [
                sample.to_dict() for sample in self.cooling_rate_samples
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThermalMassModel:
        """Create from dictionary."""
        samples = [
            CoolingRateSample.from_dict(s) for s in data.get("cooling_rate_samples", [])
        ]

        return cls(
            room_name=data["room_name"],
            cooling_rate=data.get("cooling_rate", DEFAULT_COOLING_RATE),
            cooling_rate_samples=samples,
            sample_count=data.get("sample_count", 0),
            confidence=data.get("confidence", 0.0),
            last_measurement=(
                datetime.fromisoformat(data["last_measurement"])
                if data.get("last_measurement")
                else None
            ),
        )
