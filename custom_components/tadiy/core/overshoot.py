"""Overshoot Learning for TaDIY.

Learns how much rooms typically overshoot their target temperature
and applies compensation to prevent overheating.

Especially useful for:
- Old radiators with high thermal mass
- On/Off TRVs (like Moes) that can't modulate
- Large rooms with slow temperature response
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Constants
MIN_SAMPLES_FOR_COMPENSATION = 3  # Need at least 3 overshoot events before compensating
MAX_COMPENSATION = 1.5  # Maximum compensation in °C
MIN_OVERSHOOT_THRESHOLD = 0.2  # Only count as overshoot if > 0.2°C over target
LEARNING_WEIGHT = 0.3  # How much new samples affect the average (0.3 = 30% new, 70% old)
SETTLING_TIME = timedelta(minutes=10)  # Time to wait after reaching target before measuring overshoot


@dataclass
class OvershootSample:
    """A single overshoot measurement."""
    timestamp: datetime
    target_temp: float
    peak_temp: float
    overshoot: float  # peak_temp - target_temp
    outdoor_temp: float | None = None


@dataclass
class OvershootModel:
    """Learned overshoot behavior for a room."""
    
    room_name: str
    samples: list[OvershootSample] = field(default_factory=list)
    average_overshoot: float = 0.0
    compensation: float = 0.0  # How much to reduce target
    sample_count: int = 0
    last_updated: datetime | None = None
    
    # State tracking for current heating cycle
    _heating_cycle_active: bool = False
    _cycle_start_temp: float | None = None
    _cycle_target: float | None = None
    _target_reached_time: datetime | None = None
    _peak_temp_after_target: float | None = None
    
    def start_heating_cycle(self, current_temp: float, target_temp: float) -> None:
        """Mark start of a heating cycle."""
        self._heating_cycle_active = True
        self._cycle_start_temp = current_temp
        self._cycle_target = target_temp
        self._target_reached_time = None
        self._peak_temp_after_target = None
        _LOGGER.debug(
            "Room %s: Overshoot tracking started - target=%.1f, current=%.1f",
            self.room_name, target_temp, current_temp
        )
    
    def update_temperature(self, current_temp: float, outdoor_temp: float | None = None) -> None:
        """Update with current temperature reading."""
        if not self._heating_cycle_active or self._cycle_target is None:
            return
        
        now = dt_util.utcnow()
        
        # Check if we've reached the target
        if current_temp >= self._cycle_target:
            if self._target_reached_time is None:
                self._target_reached_time = now
                self._peak_temp_after_target = current_temp
                _LOGGER.debug(
                    "Room %s: Target reached at %.1f°C",
                    self.room_name, current_temp
                )
            else:
                # Track peak temperature after reaching target
                if current_temp > (self._peak_temp_after_target or 0):
                    self._peak_temp_after_target = current_temp
        
        # Check if settling time has passed and we have a peak
        if (self._target_reached_time is not None and 
            self._peak_temp_after_target is not None and
            now - self._target_reached_time >= SETTLING_TIME):
            
            # Calculate overshoot
            overshoot = self._peak_temp_after_target - self._cycle_target
            
            if overshoot >= MIN_OVERSHOOT_THRESHOLD:
                # Record this overshoot sample
                sample = OvershootSample(
                    timestamp=now,
                    target_temp=self._cycle_target,
                    peak_temp=self._peak_temp_after_target,
                    overshoot=overshoot,
                    outdoor_temp=outdoor_temp
                )
                self._add_sample(sample)
                _LOGGER.info(
                    "Room %s: Overshoot recorded - target=%.1f, peak=%.1f, overshoot=%.1f°C",
                    self.room_name, self._cycle_target, self._peak_temp_after_target, overshoot
                )
            
            # End this cycle
            self._heating_cycle_active = False
    
    def end_heating_cycle(self) -> None:
        """End heating cycle (e.g., when heating is turned off manually)."""
        self._heating_cycle_active = False
        self._cycle_start_temp = None
        self._cycle_target = None
        self._target_reached_time = None
        self._peak_temp_after_target = None
    
    def _add_sample(self, sample: OvershootSample) -> None:
        """Add a new overshoot sample and update averages."""
        self.samples.append(sample)
        self.sample_count += 1
        self.last_updated = sample.timestamp
        
        # Keep only last 20 samples
        if len(self.samples) > 20:
            self.samples = self.samples[-20:]
        
        # Update exponential moving average
        if self.sample_count == 1:
            self.average_overshoot = sample.overshoot
        else:
            self.average_overshoot = (
                LEARNING_WEIGHT * sample.overshoot + 
                (1 - LEARNING_WEIGHT) * self.average_overshoot
            )
        
        # Update compensation (only if we have enough samples)
        if self.sample_count >= MIN_SAMPLES_FOR_COMPENSATION:
            # Compensation is 80% of average overshoot, capped at MAX_COMPENSATION
            self.compensation = min(self.average_overshoot * 0.8, MAX_COMPENSATION)
            _LOGGER.info(
                "Room %s: Overshoot compensation updated to %.2f°C (avg overshoot: %.2f°C, samples: %d)",
                self.room_name, self.compensation, self.average_overshoot, self.sample_count
            )
    
    def get_compensated_target(self, target_temp: float) -> float:
        """Get target temperature with overshoot compensation applied."""
        if self.sample_count < MIN_SAMPLES_FOR_COMPENSATION:
            return target_temp  # Not enough data yet
        
        compensated = target_temp - self.compensation
        _LOGGER.debug(
            "Room %s: Overshoot compensation - target=%.1f, compensated=%.1f (comp=%.2f)",
            self.room_name, target_temp, compensated, self.compensation
        )
        return compensated
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_name": self.room_name,
            "average_overshoot": self.average_overshoot,
            "compensation": self.compensation,
            "sample_count": self.sample_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "samples": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "target_temp": s.target_temp,
                    "peak_temp": s.peak_temp,
                    "overshoot": s.overshoot,
                    "outdoor_temp": s.outdoor_temp,
                }
                for s in self.samples[-10:]  # Only save last 10 samples
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OvershootModel:
        """Create from dictionary."""
        model = cls(
            room_name=data.get("room_name", "unknown"),
            average_overshoot=data.get("average_overshoot", 0.0),
            compensation=data.get("compensation", 0.0),
            sample_count=data.get("sample_count", 0),
        )
        
        if data.get("last_updated"):
            model.last_updated = datetime.fromisoformat(data["last_updated"])
        
        # Restore samples
        for s in data.get("samples", []):
            model.samples.append(OvershootSample(
                timestamp=datetime.fromisoformat(s["timestamp"]),
                target_temp=s["target_temp"],
                peak_temp=s["peak_temp"],
                overshoot=s["overshoot"],
                outdoor_temp=s.get("outdoor_temp"),
            ))
        
        return model


class OvershootManager:
    """Manages overshoot learning for multiple rooms."""
    
    def __init__(self) -> None:
        """Initialize the manager."""
        self._models: dict[str, OvershootModel] = {}
    
    def get_or_create_model(self, room_name: str) -> OvershootModel:
        """Get or create an overshoot model for a room."""
        if room_name not in self._models:
            self._models[room_name] = OvershootModel(room_name=room_name)
        return self._models[room_name]
    
    def get_compensated_target(self, room_name: str, target_temp: float) -> float:
        """Get target with overshoot compensation for a room."""
        model = self.get_or_create_model(room_name)
        return model.get_compensated_target(target_temp)
    
    def start_heating_cycle(self, room_name: str, current_temp: float, target_temp: float) -> None:
        """Start tracking a heating cycle for a room."""
        model = self.get_or_create_model(room_name)
        model.start_heating_cycle(current_temp, target_temp)
    
    def update_temperature(self, room_name: str, current_temp: float, outdoor_temp: float | None = None) -> None:
        """Update temperature reading for a room."""
        model = self.get_or_create_model(room_name)
        model.update_temperature(current_temp, outdoor_temp)
    
    def end_heating_cycle(self, room_name: str) -> None:
        """End heating cycle for a room."""
        if room_name in self._models:
            self._models[room_name].end_heating_cycle()
    
    def get_stats(self, room_name: str) -> dict[str, Any]:
        """Get overshoot statistics for a room."""
        if room_name not in self._models:
            return {
                "sample_count": 0,
                "average_overshoot": 0.0,
                "compensation": 0.0,
                "learning_active": False,
            }
        
        model = self._models[room_name]
        return {
            "sample_count": model.sample_count,
            "average_overshoot": round(model.average_overshoot, 2),
            "compensation": round(model.compensation, 2),
            "learning_active": model.sample_count >= MIN_SAMPLES_FOR_COMPENSATION,
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert all models to dictionary for storage."""
        return {
            room_name: model.to_dict()
            for room_name, model in self._models.items()
        }
    
    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Load models from dictionary."""
        for room_name, model_data in data.items():
            self._models[room_name] = OvershootModel.from_dict(model_data)
        _LOGGER.info("Loaded overshoot data for %d rooms", len(self._models))
    
    def reset_room(self, room_name: str) -> None:
        """Reset overshoot learning for a room."""
        if room_name in self._models:
            del self._models[room_name]
            _LOGGER.info("Reset overshoot learning for room %s", room_name)
    
    def reset_all(self) -> None:
        """Reset all overshoot learning data."""
        self._models.clear()
        _LOGGER.info("Reset all overshoot learning data")
