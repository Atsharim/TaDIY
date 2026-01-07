"""Schedule models for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import MAX_TARGET_TEMP, MIN_TARGET_TEMP


@dataclass
class ScheduleEntry:
    """A single schedule entry with time and target temperature."""

    start_time: time
    target_temperature: float
    days_of_week: list[int] = field(default_factory=lambda: list(range(7)))

    def __post_init__(self) -> None:
        """Validate schedule entry after initialization."""
        if not MIN_TARGET_TEMP <= self.target_temperature <= MAX_TARGET_TEMP:
            raise ValueError(
                f"Target temperature {self.target_temperature} out of range "
                f"({MIN_TARGET_TEMP}-{MAX_TARGET_TEMP})"
            )
        if not all(0 <= day <= 6 for day in self.days_of_week):
            raise ValueError("Days of week must be between 0 (Monday) and 6 (Sunday)")
        if not self.days_of_week:
            raise ValueError("Schedule entry must have at least one day")

    def is_active_on(self, dt: datetime) -> bool:
        """Check if this entry is active on the given datetime."""
        return dt.weekday() in self.days_of_week

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "target_temperature": self.target_temperature,
            "days_of_week": self.days_of_week,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleEntry:
        """Create from dictionary."""
        return cls(
            start_time=time.fromisoformat(data["start_time"]),
            target_temperature=data["target_temperature"],
            days_of_week=data.get("days_of_week", list(range(7))),
        )


@dataclass
class RoomSchedule:
    """Schedule for a room with multiple entries."""

    room_name: str
    entries: list[ScheduleEntry] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate schedule after initialization."""
        if not self.room_name:
            raise ValueError("Room name cannot be empty")
        self.entries.sort(key=lambda e: e.start_time)
        self._check_overlaps()

    def _check_overlaps(self) -> None:
        """Check for overlapping schedule entries on the same day."""
        for i, entry1 in enumerate(self.entries):
            for entry2 in self.entries[i + 1 :]:
                overlapping_days = set(entry1.days_of_week) & set(entry2.days_of_week)
                if overlapping_days and entry1.start_time == entry2.start_time:
                    raise ValueError(
                        f"Schedule entries overlap at {entry1.start_time} "
                        f"on days {overlapping_days}"
                    )

    def get_target_temperature(self, dt: datetime | None = None) -> float | None:
        """Get the target temperature for the given datetime."""
        if not self.enabled or not self.entries:
            return None

        if dt is None:
            dt = dt_util.now()

        active_entries = [e for e in self.entries if e.is_active_on(dt)]
        if not active_entries:
            return None

        current_time = dt.time()
        
        previous_entry = None
        for entry in active_entries:
            if entry.start_time <= current_time:
                previous_entry = entry
            else:
                break

        if previous_entry:
            return previous_entry.target_temperature

        if active_entries:
            return active_entries[-1].target_temperature

        return None

    def get_next_change(self, dt: datetime | None = None) -> tuple[datetime, float] | None:
        """Get the next schedule change time and temperature."""
        if not self.enabled or not self.entries:
            return None

        if dt is None:
            dt = dt_util.now()

        active_entries = [e for e in self.entries if e.is_active_on(dt)]
        if not active_entries:
            return None

        current_time = dt.time()
        
        for entry in active_entries:
            if entry.start_time > current_time:
                next_dt = dt.replace(
                    hour=entry.start_time.hour,
                    minute=entry.start_time.minute,
                    second=entry.start_time.second,
                    microsecond=0,
                )
                return (next_dt, entry.target_temperature)

        return None

    def add_entry(self, entry: ScheduleEntry) -> None:
        """Add a schedule entry."""
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.start_time)
        self._check_overlaps()

    def remove_entry(self, start_time: time) -> bool:
        """Remove a schedule entry by start time."""
        original_length = len(self.entries)
        self.entries = [e for e in self.entries if e.start_time != start_time]
        return len(self.entries) < original_length

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "room_name": self.room_name,
            "entries": [e.to_dict() for e in self.entries],
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomSchedule:
        """Create from dictionary."""
        return cls(
            room_name=data["room_name"],
            entries=[ScheduleEntry.from_dict(e) for e in data.get("entries", [])],
            enabled=data.get("enabled", True),
        )
