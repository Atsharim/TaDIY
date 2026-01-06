"""Room model for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class RoomConfig:
    """Configuration for a single room."""
    name: str
    trv_entity_id: str
    sensor_entity_ids: List[str]
