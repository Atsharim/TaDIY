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
        import logging
        _LOGGER = logging.getLogger(__name__)

        if not self.blocks:
            # No blocks defined - this is a configuration issue
            _LOGGER.warning(
                "Schedule has no blocks defined (type=%s), returning frost protection %.1f",
                self.schedule_type,
                frost_protection_temp,
            )
            return frost_protection_temp

        # Find active block
        active_block = self.blocks[0]
        for block in self.blocks:
            if block.start_time <= current_time:
                active_block = block
            else:
                break

        _LOGGER.info(
            "DaySchedule.get_temperature: time=%s, active_block=%s->%s, frost_prot=%.1f",
            current_time.strftime("%H:%M"),
            active_block.start_time.strftime("%H:%M"),
            active_block.temperature,
            frost_protection_temp,
        )

        # Resolve special temperatures
        if isinstance(active_block.temperature, str):
            if active_block.temperature == SCHEDULE_TEMP_FROST:
                return frost_protection_temp
            elif active_block.temperature == SCHEDULE_TEMP_OFF:
                return frost_protection_temp

        return float(active_block.temperature)

    def get_next_change(self, current_time: time) -> tuple[time, float | str] | None:
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
    custom_schedules: dict[str, DaySchedule] = field(default_factory=dict)
    use_normal_for_modes: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Validate room schedule."""
        if not self.room_name:
            raise ValueError("Room name cannot be empty")

    def set_custom_schedule(self, mode: str, schedule: DaySchedule) -> None:
        """Set schedule for a custom mode."""
        self.custom_schedules[mode] = schedule

    def get_custom_schedule(self, mode: str) -> DaySchedule | None:
        """Get schedule for a custom mode."""
        return self.custom_schedules.get(mode)

    def remove_custom_schedule(self, mode: str) -> None:
        """Remove schedule for a custom mode."""
        self.custom_schedules.pop(mode, None)

    def set_use_normal(self, mode: str, use_normal: bool) -> None:
        """Set whether a mode should use normal schedule."""
        if use_normal:
            self.use_normal_for_modes.add(mode)
        else:
            self.use_normal_for_modes.discard(mode)

    def should_use_normal(self, mode: str) -> bool:
        """Check if mode should use normal schedule."""
        return mode in self.use_normal_for_modes

    def get_schedule_for_mode(
        self, mode: str, dt: datetime | None = None
    ) -> DaySchedule | None:
        """Get appropriate schedule for given mode and datetime."""
        import logging
        _LOGGER = logging.getLogger(__name__)

        if dt is None:
            dt = dt_util.now()

        # Check if mode should use normal schedule
        if self.should_use_normal(mode):
            mode = "normal"

        result = None
        if mode == "normal":
            # Weekday: Monday (0) to Friday (4)
            if dt.weekday() < 5:
                result = self.normal_weekday
                _LOGGER.info(
                    "RoomSchedule %s: mode=normal, weekday=%d -> normal_weekday (has_blocks=%s)",
                    self.room_name,
                    dt.weekday(),
                    len(result.blocks) if result else 0,
                )
            else:
                result = self.normal_weekend
                _LOGGER.info(
                    "RoomSchedule %s: mode=normal, weekday=%d -> normal_weekend (has_blocks=%s)",
                    self.room_name,
                    dt.weekday(),
                    len(result.blocks) if result else 0,
                )
        elif mode == "homeoffice":
            result = self.homeoffice_daily
            _LOGGER.info(
                "RoomSchedule %s: mode=homeoffice -> homeoffice_daily (has_blocks=%s)",
                self.room_name,
                len(result.blocks) if result else 0,
            )
        else:
            # Custom mode
            result = self.get_custom_schedule(mode)
            _LOGGER.info(
                "RoomSchedule %s: mode=%s -> custom_schedule (has_blocks=%s)",
                self.room_name,
                mode,
                len(result.blocks) if result else 0,
            )

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"room_name": self.room_name}

        if self.normal_weekday:
            result["normal_weekday"] = self.normal_weekday.to_dict()
        if self.normal_weekend:
            result["normal_weekend"] = self.normal_weekend.to_dict()
        if self.homeoffice_daily:
            result["homeoffice_daily"] = self.homeoffice_daily.to_dict()

        # Save custom schedules
        if self.custom_schedules:
            result["custom_schedules"] = {
                mode: schedule.to_dict()
                for mode, schedule in self.custom_schedules.items()
            }

        # Save use_normal flags
        if self.use_normal_for_modes:
            result["use_normal_for_modes"] = list(self.use_normal_for_modes)

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomSchedule:
        """Create from dictionary."""
        # Load custom schedules
        custom_schedules = {}
        if "custom_schedules" in data:
            for mode, schedule_data in data["custom_schedules"].items():
                custom_schedules[mode] = DaySchedule.from_dict(schedule_data)

        # Load use_normal flags
        use_normal_for_modes = set(data.get("use_normal_for_modes", []))

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
            custom_schedules=custom_schedules,
            use_normal_for_modes=use_normal_for_modes,
        )
