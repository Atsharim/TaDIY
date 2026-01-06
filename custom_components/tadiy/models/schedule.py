"""Schedule models for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from ..core.schedule import DailySchedule


@dataclass(slots=True)
class RoomSchedule:
    """Per-room schedule mapping weekdays to schedules."""
    room_name: str
    days: Dict[int, DailySchedule]  # 0=Monday .. 6=Sunday
