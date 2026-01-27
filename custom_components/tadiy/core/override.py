"""Override tracking for TaDIY integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    OVERRIDE_TIMEOUT_ALWAYS,
    OVERRIDE_TIMEOUT_DURATIONS,
    OVERRIDE_TIMEOUT_NEVER,
    OVERRIDE_TIMEOUT_NEXT_BLOCK,
    OVERRIDE_TIMEOUT_NEXT_DAY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class OverrideRecord:
    """Record of a manual temperature override."""

    entity_id: str  # TRV entity ID
    started_at: datetime  # When override was detected
    scheduled_temp: float  # Temperature from schedule
    override_temp: float  # Manual override temperature
    timeout_mode: str  # Timeout mode being used
    expires_at: datetime | None  # When override expires (None = never)

    @property
    def temperature(self) -> float:
        """Alias for override_temp for compatibility."""
        return self.override_temp

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if override has expired."""
        if self.expires_at is None:
            return False

        if current_time is None:
            current_time = dt_util.utcnow()

        return current_time >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "entity_id": self.entity_id,
            "started_at": self.started_at.isoformat(),
            "scheduled_temp": self.scheduled_temp,
            "override_temp": self.override_temp,
            "timeout_mode": self.timeout_mode,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverrideRecord:
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            scheduled_temp=data["scheduled_temp"],
            override_temp=data["override_temp"],
            timeout_mode=data["timeout_mode"],
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )


class OverrideManager:
    """Manage temperature overrides for a room."""

    def __init__(self) -> None:
        """Initialize override manager."""
        self._overrides: dict[str, OverrideRecord] = {}

    def has_override(self, entity_id: str) -> bool:
        """Check if TRV has an active override."""
        return entity_id in self._overrides

    def get_override(self, entity_id: str) -> OverrideRecord | None:
        """Get override record for a TRV."""
        return self._overrides.get(entity_id)

    def get_active_override(self) -> OverrideRecord | None:
        """
        Get any active override for this room.

        Returns:
            First found active override record, or None
        """
        if not self._overrides:
            return None

        # Return the first active override
        # Use next(iter(dict.values())) for efficiency since we just need any one
        return next(iter(self._overrides.values()))

    def create_override(
        self,
        entity_id: str,
        scheduled_temp: float,
        override_temp: float,
        timeout_mode: str,
        next_block_time: datetime | None = None,
    ) -> OverrideRecord:
        """
        Create a new override record.

        Args:
            entity_id: TRV entity ID
            scheduled_temp: Temperature from schedule
            override_temp: Manual override temperature
            timeout_mode: Timeout mode (never, 1h-4h, next_block, next_day, always)
            next_block_time: Next schedule block change time (for next_block mode)

        Returns:
            Created override record
        """
        now = dt_util.utcnow()
        expires_at = self._calculate_expiry(now, timeout_mode, next_block_time)

        override = OverrideRecord(
            entity_id=entity_id,
            started_at=now,
            scheduled_temp=scheduled_temp,
            override_temp=override_temp,
            timeout_mode=timeout_mode,
            expires_at=expires_at,
        )

        self._overrides[entity_id] = override

        _LOGGER.info(
            "Override created for %s: %.1f°C -> %.1f°C (mode: %s, expires: %s)",
            entity_id,
            scheduled_temp,
            override_temp,
            timeout_mode,
            expires_at.strftime("%H:%M:%S") if expires_at else "never",
        )

        return override

    def clear_override(self, entity_id: str) -> bool:
        """
        Clear override for a TRV.

        Returns:
            True if override was cleared, False if no override existed
        """
        if entity_id in self._overrides:
            override = self._overrides.pop(entity_id)
            _LOGGER.info(
                "Override cleared for %s (was %.1f°C)",
                entity_id,
                override.override_temp,
            )
            return True
        return False

    def clear_all_overrides(self) -> int:
        """
        Clear all overrides.

        Returns:
            Number of overrides cleared
        """
        count = len(self._overrides)
        self._overrides.clear()
        if count > 0:
            _LOGGER.info("Cleared %d override(s)", count)
        return count

    def check_expired_overrides(self) -> list[str]:
        """
        Check for expired overrides and remove them.

        Returns:
            List of entity IDs that had expired overrides
        """
        now = dt_util.utcnow()
        expired = []

        for entity_id, override in list(self._overrides.items()):
            if override.is_expired(now):
                expired.append(entity_id)
                self._overrides.pop(entity_id)
                _LOGGER.info(
                    "Override expired for %s (was %.1f°C, scheduled: %.1f°C)",
                    entity_id,
                    override.override_temp,
                    override.scheduled_temp,
                )

        return expired

    def _calculate_expiry(
        self,
        start_time: datetime,
        timeout_mode: str,
        next_block_time: datetime | None,
    ) -> datetime | None:
        """
        Calculate override expiry time based on timeout mode.

        Args:
            start_time: Override start time
            timeout_mode: Timeout mode
            next_block_time: Next schedule block change time (for next_block mode)

        Returns:
            Expiry datetime or None for never/always
        """
        if timeout_mode == OVERRIDE_TIMEOUT_NEVER:
            return None

        if timeout_mode == OVERRIDE_TIMEOUT_ALWAYS:
            # This shouldn't happen (always mode rejects overrides)
            # but handle gracefully by expiring immediately
            return start_time

        if timeout_mode in OVERRIDE_TIMEOUT_DURATIONS:
            # Fixed duration (1h-4h)
            minutes = OVERRIDE_TIMEOUT_DURATIONS[timeout_mode]
            return start_time + timedelta(minutes=minutes)

        if timeout_mode == OVERRIDE_TIMEOUT_NEXT_BLOCK:
            # Expire at next schedule block change
            if next_block_time:
                return next_block_time
            else:
                # Fallback: 2 hours if next block time not available
                _LOGGER.warning("Next block time not available, using 2h fallback")
                return start_time + timedelta(hours=2)

        if timeout_mode == OVERRIDE_TIMEOUT_NEXT_DAY:
            # Expire at midnight (start of next day)
            next_day = (start_time + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return next_day

        # Unknown mode, use default 2 hours
        _LOGGER.warning("Unknown timeout mode %s, using 2h default", timeout_mode)
        return start_time + timedelta(hours=2)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            entity_id: override.to_dict()
            for entity_id, override in self._overrides.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverrideManager:
        """Create from dictionary."""
        manager = cls()
        for entity_id, override_data in data.items():
            try:
                override = OverrideRecord.from_dict(override_data)
                manager._overrides[entity_id] = override
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Failed to load override for %s: %s", entity_id, err)
        return manager
