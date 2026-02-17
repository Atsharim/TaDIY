"""TRV management logic for TaDIY.

Features:
- Update lock to prevent race conditions
- Context tracking for echo detection
- Last commanded state tracking
- Minimum command interval to avoid TRV flooding
- Detailed debug logging of all TRV commands
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from homeassistant.core import Context
from homeassistant.util import dt as dt_util

from .trv_profiles import TRVProfile, detect_trv_profile, get_profile

_LOGGER = logging.getLogger(__package__)

# Minimum interval between command batches to the same TRV.
# Prevents flooding when nothing has actually changed.
MIN_COMMAND_INTERVAL_SECONDS: int = 60


class TrvManager:
    """Handles communication with TRV devices for a room.

    Features:
    - _update_lock: Prevents concurrent updates to TRVs
    - _last_command_context: Context for echo detection
    - _last_commanded: Tracks what we last commanded to each TRV
    - Minimum command interval to avoid TRV flooding
    """

    def __init__(self, coordinator: Any) -> None:
        """Initialize the TRV manager."""
        self.coordinator = coordinator
        self.hass = coordinator.hass

        # Update lock prevents race conditions
        self._update_lock = asyncio.Lock()

        # Context for echo detection
        self._last_command_context: Context | None = None

        # Track last commanded state per TRV for drift detection
        self._last_commanded: dict[str, dict[str, Any]] = {}
        self._last_command_time: datetime | None = None

        # Track the last *applied* target/mode to skip redundant commands
        self._last_applied_target: float | None = None
        self._last_applied_should_heat: bool | None = None

        # Cached TRV profiles (detected once, reused)
        self._trv_profiles: dict[str, TRVProfile] = {}

    def _debug(self, message: str, *args: Any) -> None:
        """Log TRV debug message using coordinator's logger."""
        if hasattr(self.coordinator, "debug"):
            self.coordinator.debug("trv", message, *args)

    def is_own_context(self, context: Context | None) -> bool:
        """Check if event context matches our last command (echo detection)."""
        if context is None or self._last_command_context is None:
            return False
        return context.id == self._last_command_context.id

    def get_trv_profile(self, trv_id: str) -> TRVProfile:
        """Get (or auto-detect) the TRV profile for an entity."""
        if trv_id not in self._trv_profiles:
            state = self.hass.states.get(trv_id)
            profile_name = detect_trv_profile(trv_id, state)
            self._trv_profiles[trv_id] = get_profile(profile_name)
            self._debug(
                "%s: Detected TRV profile '%s' (%s)",
                trv_id,
                profile_name,
                self._trv_profiles[trv_id].manufacturer,
            )
        return self._trv_profiles[trv_id]

    def get_last_commanded(self, trv_id: str) -> dict[str, Any] | None:
        """Get last commanded state for a TRV."""
        return self._last_commanded.get(trv_id)

    def get_current_trv_state(self) -> dict[str, Any]:
        """Get summarized state of all TRVs in the room."""
        config = self.coordinator.room_config
        trv_entity_ids = config.trv_entity_ids

        all_targets = []
        all_modes = []

        for trv_id in trv_entity_ids:
            state = self.hass.states.get(trv_id)
            if state:
                target = state.attributes.get("temperature")
                if target is not None:
                    all_targets.append(float(target))
                all_modes.append(state.state)

        # Determine consolidated mode
        # If any TRV is in heat mode, the room is "heating"
        mode = "heat" if "heat" in all_modes else "off"

        # Primary target for display
        primary_target = all_targets[0] if all_targets else 20.0

        return {
            "mode": mode,
            "target": primary_target,
            "all_targets": all_targets,
            "all_modes": all_modes,
        }

    async def apply_target(
        self, target: float, should_heat: bool | None = None
    ) -> None:
        """Apply target temperature and HVAC mode to all TRVs.

        Skips redundant commands when target and mode are unchanged,
        and enforces a minimum interval between command batches.
        """
        # Skip if nothing changed since last apply
        if (
            self._last_applied_target is not None
            and abs(target - self._last_applied_target) < 0.1
            and self._last_applied_should_heat == should_heat
        ):
            # Enforce minimum interval even for "same" state
            if self._last_command_time is not None:
                elapsed = (dt_util.utcnow() - self._last_command_time).total_seconds()
                if elapsed < MIN_COMMAND_INTERVAL_SECONDS:
                    self._debug(
                        "Skipping redundant command (target=%.1f, heat=%s, %ds ago)",
                        target,
                        should_heat,
                        int(elapsed),
                    )
                    return

        # Acquire lock to prevent concurrent TRV updates
        async with self._update_lock:
            await self._apply_target_locked(target, should_heat)

        # Track what we applied
        self._last_applied_target = target
        self._last_applied_should_heat = should_heat

    async def _apply_target_locked(
        self, target: float, should_heat: bool | None
    ) -> None:
        """Internal method to apply target (must be called with lock held)."""
        config = self.coordinator.room_config
        frost_temp = (
            self.coordinator.hub_coordinator.get_frost_protection_temp()
            if self.coordinator.hub_coordinator
            else 5.0
        )

        # Create new context for this command batch (for echo detection)
        self._last_command_context = Context()
        self._last_command_time = dt_util.utcnow()

        trv_count = len(config.trv_entity_ids)
        self._debug(
            "Applying target %.1f to %d TRV(s) | should_heat=%s | use_hvac_off=%s | frost=%.1f",
            target,
            trv_count,
            should_heat,
            config.use_hvac_off_for_low_temp,
            frost_temp,
        )

        for trv_id in config.trv_entity_ids:
            try:
                state = self.hass.states.get(trv_id)
                if not state:
                    _LOGGER.warning("TRV %s: State unavailable, skipping", trv_id)
                    self._debug("%s: SKIPPED - state unavailable", trv_id)
                    continue

                profile = self.get_trv_profile(trv_id)
                current_hvac = state.state
                current_temp = state.attributes.get("temperature")

                # Get supported HVAC modes
                # Priority: 1) User-configured modes, 2) Device state, 3) Fallback
                if config.trv_hvac_modes is not None:
                    # User has explicitly configured HVAC modes for this room
                    supported_modes = config.trv_hvac_modes
                    self._debug(
                        "%s: Using user-configured HVAC modes: %s",
                        trv_id,
                        supported_modes,
                    )
                else:
                    # Auto-detect from device state (this is the authoritative source)
                    supported_modes = state.attributes.get(
                        "hvac_modes", ["heat", "off"]
                    )
                    self._debug(
                        "%s: Using device-reported HVAC modes: %s",
                        trv_id,
                        supported_modes,
                    )

                # Determine desired HVAC mode
                if config.use_hvac_off_for_low_temp:
                    # User wants to use HVAC "off" mode to stop heating
                    if target <= frost_temp:
                        desired_hvac = "off"
                    elif should_heat is not None:
                        desired_hvac = "heat" if should_heat else "off"
                    else:
                        desired_hvac = "heat"
                else:
                    # User does NOT want HVAC mode changes
                    # Always stay in "heat" mode, control via temperature only
                    desired_hvac = "heat"
                    if should_heat is False:
                        # Not heating → set to minimum temp to close valve
                        target = profile.min_temp
                        self._debug(
                            "%s: use_hvac_off disabled, using min_temp %.1f instead of HVAC off",
                            trv_id,
                            profile.min_temp,
                        )

                # Fallback: if TRV doesn't support the desired HVAC mode,
                # use temperature-based control instead
                if desired_hvac not in supported_modes:
                    self._debug(
                        "%s: HVAC '%s' not supported (available: %s), using temp fallback",
                        trv_id,
                        desired_hvac,
                        supported_modes,
                    )
                    if desired_hvac == "off":
                        # Can't turn off via HVAC mode — set to minimum temp
                        desired_hvac = "heat"
                        target = profile.min_temp
                else:
                    self._debug(
                        "%s: HVAC mode '%s' is supported",
                        trv_id,
                        desired_hvac,
                    )

                # Get room temp from coordinator
                room_temp = self.coordinator.get_current_temperature()

                # Get TRV's internal sensor temp
                trv_temp = state.attributes.get("current_temperature")
                if trv_temp is not None:
                    try:
                        trv_temp = float(trv_temp)
                    except (ValueError, TypeError):
                        trv_temp = None

                # Calculate calibrated target
                calibrated = target
                calibration_offset = 0.0

                # Apply calibration if we have both sensors and calibration_manager
                if (
                    room_temp
                    and trv_temp
                    and hasattr(self.coordinator, "calibration_manager")
                ):
                    calibrated = (
                        self.coordinator.calibration_manager.get_calibrated_target(
                            trv_id,
                            target,
                            room_temp,
                            trv_temp,
                            max_temp=config.max_temp
                            if hasattr(config, "max_temp")
                            else 30.0,
                        )
                    )
                    calibration_offset = calibrated - target

                # Apply HVAC mode if changed
                hvac_changed = current_hvac != desired_hvac
                if hvac_changed:
                    self._debug(
                        "%s: HVAC %s -> %s",
                        trv_id,
                        current_hvac,
                        desired_hvac,
                    )
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {"entity_id": trv_id, "hvac_mode": desired_hvac},
                        blocking=False,
                        context=self._last_command_context,
                    )

                # Apply temperature if changed
                temp_changed = (
                    current_temp is None or abs(float(current_temp) - calibrated) > 0.1
                )

                if temp_changed:
                    self._debug(
                        "%s: SET TEMP %.1f -> %.1f | HVAC: %s | Room: %.1f | TRV: %.1f",
                        trv_id,
                        float(current_temp) if current_temp else 0,
                        calibrated,
                        desired_hvac,
                        room_temp or 0,
                        trv_temp or 0,
                    )
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {"entity_id": trv_id, "temperature": calibrated},
                        blocking=False,
                        context=self._last_command_context,
                    )

                # Log calibration offset if significant
                if abs(calibration_offset) > 0.1:
                    self._debug(
                        "%s: Calibration applied | Target: %.1f | Calibrated: %.1f | Offset: %+.1f",
                        trv_id,
                        target,
                        calibrated,
                        calibration_offset,
                    )

                # Log if no changes needed
                if not hvac_changed and not temp_changed:
                    self._debug(
                        "%s: No change needed | HVAC: %s | Temp: %.1f",
                        trv_id,
                        current_hvac,
                        float(current_temp) if current_temp else 0,
                    )

                # Track what we commanded (using the FINAL CALIBRATED value)
                self._last_commanded[trv_id] = {
                    "hvac_mode": desired_hvac,
                    "temperature": calibrated,
                    "timestamp": self._last_command_time,
                }

            except Exception as err:
                _LOGGER.error("Failed to apply target to TRV %s: %s", trv_id, err)
                self._debug("%s: ERROR - %s", trv_id, err)

    def check_drift(
        self, trv_id: str, current_temp: float | None, current_mode: str
    ) -> bool:
        """Check if TRV has drifted from our last command.

        Returns True if TRV state differs significantly from what we commanded.
        """
        last = self._last_commanded.get(trv_id)
        if not last:
            return False

        # Check mode drift
        if last["hvac_mode"] != current_mode:
            self._debug(
                "%s: Mode drift detected - commanded %s, actual %s",
                trv_id,
                last["hvac_mode"],
                current_mode,
            )
            return True

        # Check temperature drift (only if we commanded heat mode)
        if last["hvac_mode"] == "heat" and last["temperature"] is not None:
            if (
                current_temp is not None
                and abs(current_temp - last["temperature"]) > 0.5
            ):
                self._debug(
                    "%s: Temp drift detected - commanded %.1f, actual %.1f",
                    trv_id,
                    last["temperature"],
                    current_temp,
                )
                return True

        return False
