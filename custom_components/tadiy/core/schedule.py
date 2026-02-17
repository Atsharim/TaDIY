"""Scheduling engine for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from typing import List


@dataclass(slots=True)
class ScheduleEntry:
    """Simple schedule entry."""
    time: time
    target_temperature: float


@dataclass(slots=True)
class DailySchedule:
    """Daily schedule definition."""
    entries: List[ScheduleEntry]
