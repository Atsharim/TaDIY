"""Early start / preheating logic for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass
class HeatUpModel:
    """Room heat-up characteristics (learned over time)."""
    
    room_name: str
    degrees_per_hour: float = 1.0  # Default: 1°C/h
    sample_count: int = 0
    last_updated: datetime | None = None
    samples: list[float] = field(default_factory=list)
    
    def update_with_measurement(
        self,
        temp_increase: float,
        time_minutes: float,
    ) -> None:
        """Update model with new heating measurement.
        
        Args:
            temp_increase: Temperature increase in °C
            time_minutes: Time taken in minutes
        """
        if time_minutes <= 0 or temp_increase <= 0:
            return
        
        # Calculate rate for this sample
        rate_per_hour = (temp_increase / time_minutes) * 60
        
        # Plausibility check (0.1 - 10 °C/h)
        if 0.1 <= rate_per_hour <= 10.0:
            self.samples.append(rate_per_hour)
            
            # Keep only the last 20 samples
            if len(self.samples) > 20:
                self.samples.pop(0)
            
            # Calculate moving average
            self.degrees_per_hour = sum(self.samples) / len(self.samples)
            self.sample_count += 1
            self.last_updated = dt_util.utcnow()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_name": self.room_name,
            "degrees_per_hour": self.degrees_per_hour,
            "sample_count": self.sample_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "samples": self.samples,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeatUpModel:
        """Create from dictionary."""
        last_updated = None
        if data.get("last_updated"):
            last_updated = dt_util.parse_datetime(data["last_updated"])
        
        return cls(
            room_name=data["room_name"],
            degrees_per_hour=data.get("degrees_per_hour", 1.0),
            sample_count=data.get("sample_count", 0),
            last_updated=last_updated,
            samples=data.get("samples", []),
        )


class EarlyStartCalculator:
    """Calculate optimal heating start time (Tado-like)."""

    def __init__(self, heat_up_model: HeatUpModel) -> None:
        """Initialize calculator with room heating model."""
        self.model = heat_up_model

    def calculate_start_time(
        self,
        target_time: datetime,
        current_temp: float,
        target_temp: float,
        outdoor_temp: float | None = None,
    ) -> datetime:
        """Calculate when to start heating to reach target at target_time.
        
        Args:
            target_time: Desired time to reach target temperature
            current_temp: Current room temperature
            target_temp: Desired temperature
            outdoor_temp: Outdoor temperature (for compensation)
            
        Returns:
            Datetime when heating should start
        """
        if target_temp <= current_temp:
            return target_time  # Already reached
        
        temp_diff = target_temp - current_temp
        
        # Heating rate with outdoor temperature compensation
        effective_rate = self.model.degrees_per_hour
        if outdoor_temp is not None and outdoor_temp < 0:
            # Slower heating in frost (20% reduction)
            effective_rate *= 0.8
        
        # Calculate required time
        hours_needed = temp_diff / effective_rate
        minutes_needed = int(hours_needed * 60)
        
        # Safety buffer (10%, min 5 min)
        safety_buffer = max(5, int(minutes_needed * 0.1))
        total_minutes = minutes_needed + safety_buffer
        
        # Calculate start time
        start_time = target_time - timedelta(minutes=total_minutes)
        
        # Don't start in the past
        now = dt_util.utcnow()
        if start_time < now:
            return now
        
        return start_time

    def should_start_heating_now(
        self,
        scheduled_target_time: datetime,
        current_temp: float,
        target_temp: float,
        outdoor_temp: float | None = None,
    ) -> bool:
        """Check if heating should start now for scheduled time.
        
        Args:
            scheduled_target_time: When target temp should be reached
            current_temp: Current temperature
            target_temp: Target temperature
            outdoor_temp: Outdoor temperature
            
        Returns:
            True if heating should start now
        """
        start_time = self.calculate_start_time(
            scheduled_target_time,
            current_temp,
            target_temp,
            outdoor_temp,
        )
        
        now = dt_util.utcnow()
        return now >= start_time

    def estimate_reach_time(
        self,
        current_temp: float,
        target_temp: float,
        outdoor_temp: float | None = None,
    ) -> datetime:
        """Estimate when target temperature will be reached if heating starts now.
        
        Args:
            current_temp: Current temperature
            target_temp: Target temperature
            outdoor_temp: Outdoor temperature
            
        Returns:
            Estimated datetime when target is reached
        """
        if target_temp <= current_temp:
            return dt_util.utcnow()
        
        temp_diff = target_temp - current_temp
        
        effective_rate = self.model.degrees_per_hour
        if outdoor_temp is not None and outdoor_temp < 0:
            effective_rate *= 0.8
        
        hours_needed = temp_diff / effective_rate
        minutes_needed = int(hours_needed * 60)
        
        return dt_util.utcnow() + timedelta(minutes=minutes_needed)


def calculate_adaptive_setpoint(
    target_temp: float,
    outdoor_temp: float | None,
    window_open: bool,
) -> float:
    """Calculate adaptive setpoint based on conditions.
    
    Tado-like: Lower setpoint slightly when outdoor is warm,
    or when energy-saving is beneficial.
    
    Args:
        target_temp: User's target temperature
        outdoor_temp: Outdoor temperature
        window_open: Window state
        
    Returns:
        Adjusted setpoint
    """
    if window_open:
        return 5.0  # Frost protection when window open
    
    adjusted = target_temp
    
    # Outdoor compensation
    if outdoor_temp is not None:
        if outdoor_temp > 15:
            # Warm outside: heat less
            adjusted -= 0.5
        elif outdoor_temp < -5:
            # Very cold: preheat more
            adjusted += 0.5
    
    # Limits
    return max(5.0, min(30.0, adjusted))
