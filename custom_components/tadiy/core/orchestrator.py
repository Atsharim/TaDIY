"""Room orchestration and decision logic for TaDIY."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from ..coordinator import TaDIYRoomCoordinator

_LOGGER = logging.getLogger(__name__)

class RoomOrchestrator:
    """The brain of room-level control."""

    def __init__(self, room_coordinator: TaDIYRoomCoordinator) -> None:
        """Initialize."""
        self.coordinator = room_coordinator
        self.room_config = room_coordinator.room_config
        self._last_user_interaction: datetime | None = None
        self._interaction_grace_seconds = 5

    def notify_user_interaction(self) -> None:
        """Called when a user manually changes temperature or mode."""
        self._last_user_interaction = dt_util.utcnow()
        self.coordinator.debug("rooms", "User interaction detected - starting %ds grace period", self._interaction_grace_seconds)

    def is_in_grace_period(self) -> bool:
        """Check if we are currently in the user interaction grace period."""
        if not self._last_user_interaction:
            return False
        
        delta = (dt_util.utcnow() - self._last_user_interaction).total_seconds()
        return delta < self._interaction_grace_seconds

    def calculate_target_temperature(
        self, 
        scheduled_target: float | None, 
        active_override_target: float | None,
        hub_mode: str,
        outdoor_temp: float | None,
        window_should_stop: bool
    ) -> tuple[float, bool]:
        """
        Calculate the final target temperature and whether it must be enforced.
        
        Returns:
            (target_temperature, enforce_target)
        """
        from ..const import DEFAULT_FROST_PROTECTION_TEMP

        # Get frost protection temp from hub
        frost_protection = DEFAULT_FROST_PROTECTION_TEMP
        if self.coordinator.hub_coordinator:
            frost_protection = self.coordinator.hub_coordinator.get_frost_protection_temp()

        # 1. Window Open (Highest Priority)
        if window_should_stop:
            self.coordinator.debug("rooms", "Target: Window open - enforcing frost protection %.1f°C", frost_protection)
            return frost_protection, True

        # 2. Away Mode (Hub level away) - use room's away temperature
        if self.coordinator.hub_coordinator and self.coordinator.hub_coordinator.should_reduce_heating_for_away():
            away_temp = self.room_config.away_temperature
            self.coordinator.debug("rooms", "Target: Away mode - enforcing away temperature %.1f°C", away_temp)
            return away_temp, True

        # 3. Outdoor Temperature Threshold (Heat below outside)
        if (
            outdoor_temp is not None
            and self.room_config.dont_heat_below_outdoor > 0
            and outdoor_temp >= self.room_config.dont_heat_below_outdoor
        ):
            self.coordinator.debug("rooms", "Target: Outdoor temp %.1f >= threshold %.1f - enforcing frost protection %.1f°C", 
                                  outdoor_temp, self.room_config.dont_heat_below_outdoor, frost_protection)
            return frost_protection, True

        # 4. Manual Hub Mode (complete manual control - no schedule enforcement)
        if hub_mode == "manual":
            # In true manual mode, if there's an override, use it
            if active_override_target is not None:
                self.coordinator.debug("rooms", "Target: Manual mode with override %.1f°C", active_override_target)
                return active_override_target, True
            # Otherwise, don't enforce - let TRV keep its current setting
            self.coordinator.debug("rooms", "Target: Manual mode - no enforcement")
            return None, False

        # 5. Active Override (user set a different temperature than schedule)
        if active_override_target is not None:
            self.coordinator.debug("rooms", "Target: Using active override %.1f°C", active_override_target)
            return active_override_target, True

        # 6. Schedule (normal operation)
        if scheduled_target is not None:
            self.coordinator.debug("rooms", "Target: Using scheduled target %.1f°C", scheduled_target)
            return scheduled_target, True

        # 7. Fallback - no schedule defined for this room/mode
        self.coordinator.debug("rooms", "Target: No schedule found, using default 20°C")
        return 20.0, True  # Enforce a sensible default

    def calculate_heating_decision(
        self, 
        fused_temp: float | None, 
        target_temp: float,
        hvac_mode: str
    ) -> bool:
        """Determine if heating should be active based on current state."""
        if fused_temp is None or target_temp is None:
            return False

        # If HVAC is OFF, we don't heat unless it's frost protection (safety usually handled above)
        if hvac_mode == "off":
             return False

        # Basic hysteresis / PID check
        should_heat, _ = self.coordinator.heating_controller.should_heat(
            fused_temp, target_temp
        )
        
        return should_heat
