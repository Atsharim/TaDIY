"""Room model for TaDIY."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class RoomConfig:
    """Configuration for a single room."""
    name: str
    trv_entity_id: str
    temp_sensor_ids: List[str] = None
    window_sensor_ids: List[str] = None
    weather_entity_id: str = ""
    window_open_timeout: int = 300  # Sekunden
    window_close_timeout: int = 900  # Sekunden

    def __post_init__(self) -> None:
        """Post-init setup."""
        self.temp_sensor_ids = self.temp_sensor_ids or []
        self.window_sensor_ids = self.window_sensor_ids or []
