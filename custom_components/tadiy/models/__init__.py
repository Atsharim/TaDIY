"""Data models for TaDIY integration."""
from __future__ import annotations

from .room import RoomConfig, RoomData
from .schedule import RoomSchedule, ScheduleEntry

__all__ = [
    "RoomConfig",
    "RoomData",
    "RoomSchedule",
    "ScheduleEntry",
]
