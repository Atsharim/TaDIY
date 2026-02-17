"""Location-based control for TaDIY integration.

Provides gradual temperature reduction when everyone leaves:
  0-30 min away  → scheduled target (no change)
  30-120 min     → -2°C from scheduled target
  >120 min       → away_temperature (full reduction)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Gradual reduction thresholds (seconds)
AWAY_GRACE_PERIOD: int = 1800  # 30 min: no reduction
AWAY_PARTIAL_PERIOD: int = 7200  # 2 h: partial reduction
AWAY_PARTIAL_REDUCTION: float = 2.0  # °C to reduce during partial period


@dataclass
class LocationState:
    """Location state for person tracking."""

    anyone_home: bool = False
    person_count_home: int = 0
    person_count_total: int = 0
    persons_home: list[str] = None
    persons_away: list[str] = None
    last_updated: datetime = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.persons_home is None:
            self.persons_home = []
        if self.persons_away is None:
            self.persons_away = []
        if self.last_updated is None:
            self.last_updated = dt_util.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anyone_home": self.anyone_home,
            "person_count_home": self.person_count_home,
            "person_count_total": self.person_count_total,
            "persons_home": self.persons_home,
            "persons_away": self.persons_away,
            "last_updated": self.last_updated.isoformat(),
        }


class LocationManager:
    """Manage location-based control."""

    def __init__(
        self,
        hass: HomeAssistant,
        person_entity_ids: list[str],
        debug_callback=None,
    ) -> None:
        """Initialize location manager."""
        self.hass = hass
        self.person_entity_ids = person_entity_ids or []
        self._location_state = LocationState()
        self._manual_override: bool | None = (
            None  # None = auto, True = force home, False = force away
        )
        self._debug_fn = debug_callback
        self._away_since: datetime | None = None  # When everyone left

    def get_location_state(self) -> LocationState:
        """Get current location state."""
        return self._location_state

    def set_manual_override(self, override: bool | None) -> None:
        """
        Set manual override for location detection.

        Args:
            override: None = auto detect, True = force home, False = force away
        """
        self._manual_override = override
        if override is None:
            _LOGGER.info("Location override cleared, using automatic detection")
        elif override:
            _LOGGER.info("Location override: forced to HOME")
        else:
            _LOGGER.info("Location override: forced to AWAY")

    def update_location_state(self) -> LocationState:
        """
        Update location state based on person entities.

        Returns:
            Updated location state
        """
        # Check for manual override
        if self._manual_override is not None:
            self._location_state = LocationState(
                anyone_home=self._manual_override,
                person_count_home=len(self.person_entity_ids)
                if self._manual_override
                else 0,
                person_count_total=len(self.person_entity_ids),
                persons_home=self.person_entity_ids if self._manual_override else [],
                persons_away=[] if self._manual_override else self.person_entity_ids,
                last_updated=dt_util.utcnow(),
            )
            return self._location_state

        # No person entities configured
        if not self.person_entity_ids:
            self._location_state = LocationState(
                anyone_home=True,  # Default to home if no persons configured
                person_count_home=0,
                person_count_total=0,
                persons_home=[],
                persons_away=[],
                last_updated=dt_util.utcnow(),
            )
            return self._location_state

        # Check each person entity
        persons_home = []
        persons_away = []

        for entity_id in self.person_entity_ids:
            state = self.hass.states.get(entity_id)
            if state is None:
                _LOGGER.warning("Person entity %s not found", entity_id)
                continue

            # Person is home if state is "home" (case-insensitive)
            if state.state.lower() == "home":
                persons_home.append(entity_id)
            else:
                persons_away.append(entity_id)

        # Update location state
        self._location_state = LocationState(
            anyone_home=len(persons_home) > 0,
            person_count_home=len(persons_home),
            person_count_total=len(self.person_entity_ids),
            persons_home=persons_home,
            persons_away=persons_away,
            last_updated=dt_util.utcnow(),
        )

        # Track when away mode started/ended
        if self._location_state.anyone_home:
            if self._away_since is not None:
                self._debug(
                    "Someone returned home after %d min away",
                    int((dt_util.utcnow() - self._away_since).total_seconds() / 60),
                )
            self._away_since = None
        elif self._away_since is None:
            self._away_since = dt_util.utcnow()
            self._debug("Everyone left - away timer started")

        self._debug(
            "Location updated: %d/%d home (%s)",
            self._location_state.person_count_home,
            self._location_state.person_count_total,
            "anyone_home" if self._location_state.anyone_home else "all_away",
        )

        return self._location_state

    def _debug(self, message: str, *args) -> None:
        """Log debug message if callback is set."""
        if self._debug_fn:
            self._debug_fn("hub", message, args)
        else:
            _LOGGER.debug(message, *args)

    def is_away_mode_active(self) -> bool:
        """Check if away mode should be active (nobody home)."""
        active = not self._location_state.anyone_home
        self._debug(
            "Away mode: %s (home=%d/%d, override=%s)",
            "ACTIVE" if active else "inactive",
            self._location_state.person_count_home,
            self._location_state.person_count_total,
            self._manual_override,
        )
        return active

    def should_reduce_heating(self) -> bool:
        """Check if heating should be reduced due to away mode."""
        return self.is_away_mode_active()

    def get_away_duration_seconds(self) -> float:
        """Return how long everyone has been away (0 if someone is home)."""
        if self._away_since is None:
            return 0.0
        return (dt_util.utcnow() - self._away_since).total_seconds()

    def get_gradual_away_target(
        self, scheduled_target: float, away_target: float
    ) -> float:
        """Calculate gradually reduced target based on away duration.

        Phase 1 (0-30 min):   keep scheduled target (grace period)
        Phase 2 (30-120 min): reduce by AWAY_PARTIAL_REDUCTION °C
        Phase 3 (>120 min):   use full away_target
        """
        duration = self.get_away_duration_seconds()

        if duration < AWAY_GRACE_PERIOD:
            self._debug(
                "Away gradual: grace period (%d/%d min) -> keep %.1f°C",
                int(duration / 60),
                AWAY_GRACE_PERIOD // 60,
                scheduled_target,
            )
            return scheduled_target

        if duration < AWAY_PARTIAL_PERIOD:
            partial = max(away_target, scheduled_target - AWAY_PARTIAL_REDUCTION)
            self._debug(
                "Away gradual: partial reduction (%d min) -> %.1f°C (-%s°C)",
                int(duration / 60),
                partial,
                AWAY_PARTIAL_REDUCTION,
            )
            return partial

        self._debug(
            "Away gradual: full reduction (%d min) -> %.1f°C",
            int(duration / 60),
            away_target,
        )
        return away_target
