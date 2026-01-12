"""Schedule models for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    SCHEDULE_TEMP_FROST,
    SCHEDULE_TEMP_OFF,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKDAY,
    SCHEDULE_TYPE_WEEKEND,
)


@dataclass
class ScheduleBlock:
    """A single schedule block with start time and temperature."""

    start_time: time
    temperature: float | str

    def __post_init__(self) -> None:
        """Validate schedule block after initialization."""
        if isinstance(self.temperature, str):
            if self.temperature not in (SCHEDULE_TEMP_FROST, SCHEDULE_TEMP_OFF):
                raise ValueError(
                    "Invalid temperature string: {}. Must be 'frost' or 'off' or a numeric value.".format(
                        self.temperature
                    )
                )
        elif not MIN_TARGET_TEMP <= self.temperature <= MAX_TARGET_TEMP:
            raise ValueError(
                "Temperature {}°C out of range ({}°C to {}°C)".format(
                    self.temperature, MIN_TARGET_TEMP, MAX_TARGET_TEMP
                )
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleBlock:
        """Create from dictionary."""
        return cls(
            start_time=time.fromisoformat(data["start_time"]),
            temperature=data["temperature"],
        )


@dataclass
class DaySchedule:
    """Schedule for a single day type (weekday/weekend/daily)."""

    schedule_type: str
    blocks: list[ScheduleBlock] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate and sort schedule after initialization."""
        if self.schedule_type not in (
            SCHEDULE_TYPE_WEEKDAY,
            SCHEDULE_TYPE_WEEKEND,
            SCHEDULE_TYPE_DAILY,
        ):
            raise ValueError("Invalid schedule type: {}".format(self.schedule_type))

        # Sort blocks by start time
        self.blocks.sort(key=lambda b: b.start_time)

        # Validate coverage
        self._validate_coverage()

    def _validate_coverage(self) -> None:
        """Validate that schedule covers full day without gaps."""
        if not self.blocks:
            return

        # Must start at 00:00
        if self.blocks[0].start_time != time(0, 0):
            raise ValueError("First block must start at 00:00")

        # Check for gaps between blocks
        for i in range(len(self.blocks) - 1):
            current_end = self._next_block_time(self.blocks[i].start_time, i)
            next_start = self.blocks[i + 1].start_time

            if current_end != next_start:
                raise ValueError(
                    "Gap detected between {} and {}. Blocks must be continuous.".format(
                        current_end, next_start
                    )
                )

    def _next_block_time(self, current: time, index: int) -> time:
        """Calculate when the next block should start."""
        if index < len(self.blocks) - 1:
            return self.blocks[index + 1].start_time
        return time(0, 0)

    def get_temperature(
        self, current_time: time, frost_protection_temp: float
    ) -> float:
        """Get temperature for given time."""
        if not self.blocks:
            return frost_protection_temp

        # Find active block
        active_block = self.blocks[0]
        for block in self.blocks:
            if block.start_time <= current_time:
                active_block = block
            else:
                break

        # Resolve special temperatures
        if isinstance(active_block.temperature, str):
            if active_block.temperature == SCHEDULE_TEMP_FROST:
                return frost_protection_temp
            elif active_block.temperature == SCHEDULE_TEMP_OFF:
                return frost_protection_temp

        return float(active_block.temperature)

    def get_next_change(
        self, current_time: time
    ) -> tuple[time, float | str] | None:
        """Get next schedule change time and temperature."""
        if not self.blocks:
            return None

        for block in self.blocks:
            if block.start_time > current_time:
                return (block.start_time, block.temperature)

        # No more changes today, next change is first block tomorrow
        return (self.blocks[0].start_time, self.blocks[0].temperature)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schedule_type": self.schedule_type,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DaySchedule:
        """Create from dictionary."""
        return cls(
            schedule_type=data["schedule_type"],
            blocks=[ScheduleBlock.from_dict(b) for b in data.get("blocks", [])],
        )


@dataclass
class RoomSchedule:
    """Complete schedule configuration for a room across all modes."""

    room_name: str
    normal_weekday: DaySchedule | None = None
    normal_weekend: DaySchedule | None = None
    homeoffice_daily: DaySchedule | None = None

    def __post_init__(self) -> None:
        """Validate room schedule."""
        if not self.room_name:
            raise ValueError("Room name cannot be empty")

    def get_schedule_for_mode(
        self, mode: str, dt: datetime | None = None
    ) -> DaySchedule | None:
        """Get appropriate schedule for given mode and datetime."""
        if dt is None:
            dt = dt_util.now()

        if mode == "normal":
            # Weekday: Monday (0) to Friday (4)
            if dt.weekday() < 5:
                return self.normal_weekday
            else:
                return self.normal_weekend
        elif mode == "homeoffice":
            return self.homeoffice_daily
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"room_name": self.room_name}

        if self.normal_weekday:
            result["normal_weekday"] = self.normal_weekday.to_dict()
        if self.normal_weekend:
            result["normal_weekend"] = self.normal_weekend.to_dict()
        if self.homeoffice_daily:
            result["homeoffice_daily"] = self.homeoffice_daily.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomSchedule:
        """Create from dictionary."""
        return cls(
            room_name=data["room_name"],
            normal_weekday=(
                DaySchedule.from_dict(data["normal_weekday"])
                if "normal_weekday" in data
                else None
            ),
            normal_weekend=(
                DaySchedule.from_dict(data["normal_weekend"])
                if "normal_weekend" in data
                else None
            ),
            homeoffice_daily=(
                DaySchedule.from_dict(data["homeoffice_daily"])
                if "homeoffice_daily" in data
                else None
            ),
        )
