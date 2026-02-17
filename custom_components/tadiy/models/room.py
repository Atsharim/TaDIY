"""Room model for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..core.window import WindowState


@dataclass
class RoomConfig:
    """Configuration for a single room."""
    
    name: str
    trv_entity_ids: list[str]
    main_temp_sensor_id: str
    window_sensor_ids: list[str] = field(default_factory=list)
    weather_entity_id: str = ""
    outdoor_sensor_id: str = ""
    window_open_timeout: int = 300
    window_close_timeout: int = 900
    dont_heat_below_outdoor: float = 10.0
    use_early_start: bool = True
    learn_heating_rate: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trv_entity_ids": self.trv_entity_ids,
            "main_temp_sensor_id": self.main_temp_sensor_id,
            "window_sensor_ids": self.window_sensor_ids,
            "weather_entity_id": self.weather_entity_id,
            "outdoor_sensor_id": self.outdoor_sensor_id,
            "window_open_timeout": self.window_open_timeout,
            "window_close_timeout": self.window_close_timeout,
            "dont_heat_below_outdoor": self.dont_heat_below_outdoor,
            "use_early_start": self.use_early_start,
            "learn_heating_rate": self.learn_heating_rate,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomConfig:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            trv_entity_ids=data["trv_entity_ids"],
            main_temp_sensor_id=data["main_temp_sensor_id"],
            window_sensor_ids=data.get("window_sensor_ids", []),
            weather_entity_id=data.get("weather_entity_id", ""),
            outdoor_sensor_id=data.get("outdoor_sensor_id", ""),
            window_open_timeout=data.get("window_open_timeout", 300),
            window_close_timeout=data.get("window_close_timeout", 900),
            dont_heat_below_outdoor=data.get("dont_heat_below_outdoor", 10.0),
            use_early_start=data.get("use_early_start", True),
            learn_heating_rate=data.get("learn_heating_rate", True),
        )


@dataclass
class RoomData:
    """Current runtime data for a room."""
    
    room_name: str
    current_temperature: float
    main_sensor_temperature: float
    trv_temperatures: list[float]
    window_state: WindowState
    outdoor_temperature: float | None = None
    target_temperature: float | None = None
    hvac_mode: str = "heat"
    last_update: datetime | None = None
    heating_active: bool = False
    heating_rate: float = 1.0  # °C per hour (learned)
    
    @property
    def is_heating_blocked(self) -> bool:
        """Check if heating is blocked (window open, outdoor temp)."""
        if self.window_state.is_open:
            return True
        if self.outdoor_temperature and self.outdoor_temperature > 20.0:
            return True
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "room_name": self.room_name,
            "current_temperature": self.current_temperature,
            "main_sensor_temperature": self.main_sensor_temperature,
            "trv_temperatures": self.trv_temperatures,
            "window_open": self.window_state.is_open,
            "outdoor_temperature": self.outdoor_temperature,
            "target_temperature": self.target_temperature,
            "hvac_mode": self.hvac_mode,
            "heating_active": self.heating_active,
            "heating_rate": self.heating_rate,
        }
