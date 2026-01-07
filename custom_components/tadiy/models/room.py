"""Room data models for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_HEATING_RATE,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from ..core.window import WindowState


@dataclass
class RoomConfig:
    """Configuration for a room."""

    name: str
    trv_entity_ids: list[str]
    main_temp_sensor_id: str
    window_sensor_ids: list[str] = field(default_factory=list)
    outdoor_sensor_id: str = ""
    weather_entity_id: str = ""
    window_open_timeout: int = DEFAULT_WINDOW_OPEN_TIMEOUT
    window_close_timeout: int = DEFAULT_WINDOW_CLOSE_TIMEOUT
    dont_heat_below_outdoor: float = 20.0
    use_early_start: bool = True
    learn_heating_rate: bool = True
    use_humidity_compensation: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.name:
            raise ValueError("Room name cannot be empty")
        if not self.trv_entity_ids:
            raise ValueError(f"Room {self.name} must have at least one TRV")
        if not self.main_temp_sensor_id:
            raise ValueError(f"Room {self.name} must have a main temperature sensor")
        if self.window_open_timeout < 0:
            raise ValueError(f"Room {self.name} window_open_timeout must be >= 0")
        if self.window_close_timeout < 0:
            raise ValueError(f"Room {self.name} window_close_timeout must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trv_entity_ids": self.trv_entity_ids,
            "main_temp_sensor_id": self.main_temp_sensor_id,
            "window_sensor_ids": self.window_sensor_ids,
            "outdoor_sensor_id": self.outdoor_sensor_id,
            "weather_entity_id": self.weather_entity_id,
            "window_open_timeout": self.window_open_timeout,
            "window_close_timeout": self.window_close_timeout,
            "dont_heat_below_outdoor": self.dont_heat_below_outdoor,
            "use_early_start": self.use_early_start,
            "learn_heating_rate": self.learn_heating_rate,
            "use_humidity_compensation": self.use_humidity_compensation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomConfig:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            trv_entity_ids=data["trv_entity_ids"],
            main_temp_sensor_id=data["main_temp_sensor_id"],
            window_sensor_ids=data.get("window_sensor_ids", []),
            outdoor_sensor_id=data.get("outdoor_sensor_id", ""),
            weather_entity_id=data.get("weather_entity_id", ""),
            window_open_timeout=data.get("window_open_timeout", DEFAULT_WINDOW_OPEN_TIMEOUT),
            window_close_timeout=data.get("window_close_timeout", DEFAULT_WINDOW_CLOSE_TIMEOUT),
            dont_heat_below_outdoor=data.get("dont_heat_below_outdoor", 20.0),
            use_early_start=data.get("use_early_start", True),
            learn_heating_rate=data.get("learn_heating_rate", True),
            use_humidity_compensation=data.get("use_humidity_compensation", False),
        )


@dataclass
class RoomData:
    """Current state data for a room."""

    room_name: str
    current_temperature: float
    main_sensor_temperature: float
    trv_temperatures: list[float]
    window_state: WindowState
    outdoor_temperature: float | None
    target_temperature: float | None
    hvac_mode: str
    last_update: datetime = field(default_factory=dt_util.utcnow)
    heating_active: bool = False
    heating_rate: float = DEFAULT_HEATING_RATE

    def __post_init__(self) -> None:
        """Validate data after initialization."""
        if self.target_temperature is not None:
            if not MIN_TARGET_TEMP <= self.target_temperature <= MAX_TARGET_TEMP:
                raise ValueError(
                    f"Target temperature {self.target_temperature} out of range "
                    f"({MIN_TARGET_TEMP}-{MAX_TARGET_TEMP})"
                )
        if self.heating_rate < 0:
            raise ValueError(f"Heating rate {self.heating_rate} must be >= 0")

    @property
    def is_heating_blocked(self) -> bool:
        """Check if heating is blocked by any condition."""
        return self.window_state.heating_should_stop or self.hvac_mode == "off"

    @property
    def temperature_delta(self) -> float | None:
        """Get difference between target and current temperature."""
        if self.target_temperature is None:
            return None
        return self.target_temperature - self.current_temperature

    @property
    def is_heating_needed(self) -> bool:
        """Check if heating is needed."""
        if self.target_temperature is None:
            return False
        return self.current_temperature < self.target_temperature

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "room_name": self.room_name,
            "current_temperature": self.current_temperature,
            "main_sensor_temperature": self.main_sensor_temperature,
            "trv_temperatures": self.trv_temperatures,
            "window_state": {
                "is_open": self.window_state.is_open,
                "heating_should_stop": self.window_state.heating_should_stop,
                "reason": self.window_state.reason,
                "last_change": (
                    self.window_state.last_change.isoformat()
                    if self.window_state.last_change
                    else None
                ),
                "timeout_active": self.window_state.timeout_active,
            },
            "outdoor_temperature": self.outdoor_temperature,
            "target_temperature": self.target_temperature,
            "hvac_mode": self.hvac_mode,
            "last_update": self.last_update.isoformat(),
            "heating_active": self.heating_active,
            "heating_rate": self.heating_rate,
            "is_heating_blocked": self.is_heating_blocked,
            "temperature_delta": self.temperature_delta,
            "is_heating_needed": self.is_heating_needed,
        }
