"""Room data models for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_AWAY_TEMPERATURE,
    DEFAULT_HEATING_RATE,
    DEFAULT_TRV_MAX_TEMP,
    DEFAULT_TRV_MIN_TEMP,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
)
from .window import WindowState


@dataclass
class RoomConfig:
    """Configuration for a room."""

    name: str
    trv_entity_ids: list[str]
    main_temp_sensor_id: str
    humidity_sensor_id: str = ""
    window_sensor_ids: list[str] = field(default_factory=list)
    outdoor_sensor_id: str = ""
    weather_entity_id: str = ""
    window_open_timeout: int = DEFAULT_WINDOW_OPEN_TIMEOUT
    window_close_timeout: int = DEFAULT_WINDOW_CLOSE_TIMEOUT
    dont_heat_below_outdoor: float = (
        0.0  # 0 = disabled, otherwise outdoor temp threshold
    )
    use_early_start: bool = True
    learn_heating_rate: bool = True
    early_start_offset: int | None = (
        None  # Room override (minutes), None = use hub setting
    )
    early_start_max: int | None = (
        None  # Room override (minutes), None = use hub setting
    )
    override_timeout: str | None = (
        None  # Room override timeout mode, None = use hub setting
    )
    hysteresis: float = 0.3  # Temperature deadband in °C
    use_pid_control: bool = False  # PID controller disabled by default
    pid_kp: float = 0.5  # Proportional gain
    pid_ki: float = 0.01  # Integral gain
    pid_kd: float = 0.1  # Derivative gain
    use_heating_curve: bool = False  # Heating curve disabled by default
    heating_curve_slope: float = 0.5  # Curve slope (°C indoor per °C outdoor)
    use_humidity_compensation: bool = False
    use_hvac_off_for_low_temp: bool = (
        False  # Use HVAC off instead of low temp to stop heating
    )
    trv_hvac_modes: list[str] | None = (
        None  # Explicit HVAC modes for TRV (None = auto-detect from device)
    )
    use_weather_prediction: bool = False  # Weather-based predictive heating
    use_room_coupling: bool = False  # Multi-room heat coupling
    adjacent_rooms: list[str] = field(default_factory=list)  # Names of adjacent rooms
    coupling_strength: float = 0.5  # Heat coupling factor (0.0-1.0)
    away_temperature: float = DEFAULT_AWAY_TEMPERATURE  # Per-room away mode temperature
    trv_min_temp: float = DEFAULT_TRV_MIN_TEMP  # TRV hardware minimum temperature
    trv_max_temp: float = DEFAULT_TRV_MAX_TEMP  # TRV hardware maximum temperature

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.name:
            raise ValueError("Room name cannot be empty")
        if not self.trv_entity_ids:
            raise ValueError("Room {} must have at least one TRV".format(self.name))
        # Note: main_temp_sensor_id is optional - TRVs can report their own temperature
        if self.window_open_timeout < 0:
            raise ValueError(
                "Room {} window_open_timeout must be >= 0".format(self.name)
            )
        if self.window_close_timeout < 0:
            raise ValueError(
                "Room {} window_close_timeout must be >= 0".format(self.name)
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trv_entity_ids": self.trv_entity_ids,
            "main_temp_sensor_id": self.main_temp_sensor_id,
            "humidity_sensor_id": self.humidity_sensor_id,
            "window_sensor_ids": self.window_sensor_ids,
            "outdoor_sensor_id": self.outdoor_sensor_id,
            "weather_entity_id": self.weather_entity_id,
            "window_open_timeout": self.window_open_timeout,
            "window_close_timeout": self.window_close_timeout,
            "dont_heat_below_outdoor": self.dont_heat_below_outdoor,
            "use_early_start": self.use_early_start,
            "learn_heating_rate": self.learn_heating_rate,
            "early_start_offset": self.early_start_offset,
            "early_start_max": self.early_start_max,
            "override_timeout": self.override_timeout,
            "hysteresis": self.hysteresis,
            "use_pid_control": self.use_pid_control,
            "pid_kp": self.pid_kp,
            "pid_ki": self.pid_ki,
            "pid_kd": self.pid_kd,
            "use_heating_curve": self.use_heating_curve,
            "heating_curve_slope": self.heating_curve_slope,
            "use_humidity_compensation": self.use_humidity_compensation,
            "use_hvac_off_for_low_temp": self.use_hvac_off_for_low_temp,
            "trv_hvac_modes": self.trv_hvac_modes,
            "use_weather_prediction": self.use_weather_prediction,
            "use_room_coupling": self.use_room_coupling,
            "adjacent_rooms": self.adjacent_rooms,
            "coupling_strength": self.coupling_strength,
            "away_temperature": self.away_temperature,
            "trv_min_temp": self.trv_min_temp,
            "trv_max_temp": self.trv_max_temp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomConfig:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            trv_entity_ids=data["trv_entity_ids"],
            main_temp_sensor_id=data["main_temp_sensor_id"],
            humidity_sensor_id=data.get("humidity_sensor_id", ""),
            window_sensor_ids=data.get("window_sensor_ids", []),
            outdoor_sensor_id=data.get("outdoor_sensor_id", ""),
            weather_entity_id=data.get("weather_entity_id", ""),
            window_open_timeout=data.get(
                "window_open_timeout", DEFAULT_WINDOW_OPEN_TIMEOUT
            ),
            window_close_timeout=data.get(
                "window_close_timeout", DEFAULT_WINDOW_CLOSE_TIMEOUT
            ),
            dont_heat_below_outdoor=data.get("dont_heat_below_outdoor", 0.0),
            use_early_start=data.get("use_early_start", True),
            learn_heating_rate=data.get("learn_heating_rate", True),
            early_start_offset=data.get("early_start_offset"),
            early_start_max=data.get("early_start_max"),
            override_timeout=data.get("override_timeout"),
            hysteresis=data.get("hysteresis", 0.3),
            use_pid_control=data.get("use_pid_control", False),
            pid_kp=data.get("pid_kp", 0.5),
            pid_ki=data.get("pid_ki", 0.01),
            pid_kd=data.get("pid_kd", 0.1),
            use_heating_curve=data.get("use_heating_curve", False),
            heating_curve_slope=data.get("heating_curve_slope", 0.5),
            use_humidity_compensation=data.get("use_humidity_compensation", False),
            use_hvac_off_for_low_temp=data.get("use_hvac_off_for_low_temp", False),
            trv_hvac_modes=data.get("trv_hvac_modes", None),
            use_weather_prediction=data.get("use_weather_prediction", False),
            use_room_coupling=data.get("use_room_coupling", False),
            adjacent_rooms=data.get("adjacent_rooms", []),
            coupling_strength=data.get("coupling_strength", 0.5),
            away_temperature=data.get("away_temperature", DEFAULT_AWAY_TEMPERATURE),
            trv_min_temp=data.get("trv_min_temp", DEFAULT_TRV_MIN_TEMP),
            trv_max_temp=data.get("trv_max_temp", DEFAULT_TRV_MAX_TEMP),
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
    humidity: float | None = None
    last_update: datetime = field(default_factory=dt_util.utcnow)
    heating_active: bool = False
    heating_rate: float = DEFAULT_HEATING_RATE
    heating_rate_sample_count: int = 0
    heating_rate_confidence: float = 0.0
    heating_rate_last_updated: datetime | None = None
    override_count: int = 0  # Number of active overrides
    override_active: bool = False  # At least one override active

    def __post_init__(self) -> None:
        """Validate data after initialization."""
        if self.target_temperature is not None:
            if not MIN_TARGET_TEMP <= self.target_temperature <= MAX_TARGET_TEMP:
                raise ValueError(
                    "Target temperature {} out of range ({}-{})".format(
                        self.target_temperature, MIN_TARGET_TEMP, MAX_TARGET_TEMP
                    )
                )
        if self.heating_rate < 0:
            raise ValueError("Heating rate {} must be >= 0".format(self.heating_rate))

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
