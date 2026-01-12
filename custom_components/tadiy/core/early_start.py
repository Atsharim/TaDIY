"""Early start calculation with learning for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_HEATING_RATE,
    MAX_HEATING_RATE,
    MIN_HEATING_RATE,
)

_LOGGER = logging.getLogger(__name__)

LEARNING_RATE: float = 0.1
MAX_SAMPLES_FOR_AVERAGING: int = 50
MIN_TEMP_INCREASE: float = 0.05
MAX_TEMP_INCREASE_PER_MINUTE: float = 0.5


@dataclass
class HeatUpModel:
    """Model for learning heating rates."""

    room_name: str
    degrees_per_hour: float = DEFAULT_HEATING_RATE
    sample_count: int = 0
    last_updated: datetime | None = None
    _running_sum: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate heating model."""
        if not MIN_HEATING_RATE <= self.degrees_per_hour <= MAX_HEATING_RATE:
            raise ValueError(
                f"degrees_per_hour must be between {MIN_HEATING_RATE} "
                f"and {MAX_HEATING_RATE}"
            )
        self._running_sum = self.degrees_per_hour * self.sample_count

    def get_heating_rate(self) -> float:
        """Get current heating rate in °C/h."""
        return self.degrees_per_hour

    def update_with_measurement(
        self,
        temp_increase: float,
        time_minutes: float,
    ) -> None:
        """
        Update model with a new measurement.
        
        Args:
            temp_increase: Temperature increase in °C
            time_minutes: Time period in minutes
        """
        if time_minutes <= 0:
            _LOGGER.warning(
                "%s: Invalid time_minutes %.2f, skipping update",
                self.room_name,
                time_minutes,
            )
            return

        if temp_increase < MIN_TEMP_INCREASE:
            _LOGGER.debug(
                "%s: Temperature increase too small (%.3f°C), skipping",
                self.room_name,
                temp_increase,
            )
            return

        rate_per_hour = (temp_increase / time_minutes) * 60

        if not MIN_HEATING_RATE <= rate_per_hour <= MAX_HEATING_RATE:
            _LOGGER.warning(
                "%s: Heating rate %.2f°C/h out of plausible range, skipping",
                self.room_name,
                rate_per_hour,
            )
            return

        if rate_per_hour > (temp_increase / time_minutes) * 60 * 2:
            _LOGGER.warning(
                "%s: Heating rate suspiciously high (%.2f°C/h), skipping",
                self.room_name,
                rate_per_hour,
            )
            return

        old_rate = self.degrees_per_hour

        if self.sample_count < MAX_SAMPLES_FOR_AVERAGING:
            self._running_sum += rate_per_hour
            self.sample_count += 1
            self.degrees_per_hour = self._running_sum / self.sample_count
        else:
            self.degrees_per_hour = (
                (1 - LEARNING_RATE) * self.degrees_per_hour
                + LEARNING_RATE * rate_per_hour
            )
            self.sample_count += 1

        self.last_updated = dt_util.utcnow()

        _LOGGER.info(
            "%s: Heating rate updated: %.2f -> %.2f °C/h "
            "(measured: %.2f °C/h over %.1f min, sample %d)",
            self.room_name,
            old_rate,
            self.degrees_per_hour,
            rate_per_hour,
            time_minutes,
            self.sample_count,
        )

    def get_confidence(self) -> float:
        """
        Get confidence score for the learned rate (0.0 to 1.0).
        
        Returns:
            Confidence score based on sample count
        """
        if self.sample_count == 0:
            return 0.0
        if self.sample_count >= MAX_SAMPLES_FOR_AVERAGING:
            return 1.0
        return min(self.sample_count / MAX_SAMPLES_FOR_AVERAGING, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_name": self.room_name,
            "degrees_per_hour": self.degrees_per_hour,
            "sample_count": self.sample_count,
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
            "_running_sum": self._running_sum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeatUpModel:
        """Create from dictionary."""
        model = cls(
            room_name=data["room_name"],
            degrees_per_hour=data.get("degrees_per_hour", DEFAULT_HEATING_RATE),
            sample_count=data.get("sample_count", 0),
            last_updated=(
                datetime.fromisoformat(data["last_updated"])
                if data.get("last_updated")
                else None
            ),
        )
        model._running_sum = data.get("_running_sum", 0.0)
        return model


class EarlyStartCalculator:
    """Calculate early start times based on learned heating rates."""

    def __init__(self, heat_model: HeatUpModel) -> None:
        """Initialize calculator with a heating model."""
        self._heat_model = heat_model

    def calculate_start_time(
        self,
        current_temp: float,
        target_temp: float,
        target_time: datetime,
    ) -> datetime:
        """
        Calculate when to start heating to reach target by target_time.
        
        Args:
            current_temp: Current room temperature in °C
            target_temp: Target temperature in °C
            target_time: Desired time to reach target
            
        Returns:
            Datetime when heating should start
        """
        if target_temp <= current_temp:
            _LOGGER.debug(
                "%s: Already at or above target (%.1f°C >= %.1f°C)",
                self._heat_model.room_name,
                current_temp,
                target_temp,
            )
            return target_time

        temp_delta = target_temp - current_temp
        hours_needed = temp_delta / self._heat_model.degrees_per_hour

        confidence = self._heat_model.get_confidence()
        if confidence < 0.5:
            safety_factor = 1.5
            _LOGGER.debug(
                "%s: Low confidence (%.1f%%), applying safety factor %.1fx",
                self._heat_model.room_name,
                confidence * 100,
                safety_factor,
            )
            hours_needed *= safety_factor

        start_time = target_time - timedelta(hours=hours_needed)

        _LOGGER.info(
            "%s: Early start calculated: %.1f°C -> %.1f°C (Δ%.1f°C) "
            "needs %.2fh at %.2f°C/h, start at %s",
            self._heat_model.room_name,
            current_temp,
            target_temp,
            temp_delta,
            hours_needed,
            self._heat_model.degrees_per_hour,
            start_time.strftime("%H:%M:%S"),
        )

        return start_time

    def should_start_heating(
        self,
        current_temp: float,
        target_temp: float,
        target_time: datetime,
        current_time: datetime | None = None,
    ) -> bool:
        """
        Check if heating should start now to reach target by target_time.
        
        Args:
            current_temp: Current room temperature
            target_temp: Target temperature
            target_time: Desired time to reach target
            current_time: Current time (defaults to now)
            
        Returns:
            True if heating should start
        """
        if current_time is None:
            current_time = dt_util.utcnow()

        start_time = self.calculate_start_time(current_temp, target_temp, target_time)
        return current_time >= start_time