"""TRV management logic for TaDIY.

Features:
- Update lock to prevent race conditions
- Context tracking for echo detection
- Last commanded state tracking
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from homeassistant.core import Context
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__package__)


class TrvManager:
    """Handles communication with TRV devices for a room.
    
    Features:
    - _update_lock: Prevents concurrent updates to TRVs
    - _last_command_context: Context for echo detection
    - _last_commanded: Tracks what we last commanded to each TRV
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

    def is_own_context(self, context: Context | None) -> bool:
        """Check if event context matches our last command (echo detection)."""
        if context is None or self._last_command_context is None:
            return False
        return context.id == self._last_command_context.id

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
            "all_modes": all_modes
        }

    async def apply_target(self, target: float, should_heat: bool | None = None) -> None:
        """Apply target temperature and HVAC mode to all TRVs.
        
        Uses update lock to prevent race conditions.
        """
        # Acquire lock to prevent concurrent TRV updates
        async with self._update_lock:
            await self._apply_target_locked(target, should_heat)

    async def _apply_target_locked(self, target: float, should_heat: bool | None) -> None:
        """Internal method to apply target (must be called with lock held)."""
        config = self.coordinator.room_config
        frost_temp = self.coordinator.hub_coordinator.get_frost_protection_temp() if self.coordinator.hub_coordinator else 5.0
        
        # Create new context for this command batch (for echo detection)
        self._last_command_context = Context()
        self._last_command_time = dt_util.utcnow()

        for trv_id in config.trv_entity_ids:
            try:
                state = self.hass.states.get(trv_id)
                if not state:
                    _LOGGER.warning("TRV %s: State unavailable, skipping", trv_id)
                    continue

                current_hvac = state.state
                current_temp = state.attributes.get("temperature")
                
                # Determine desired HVAC mode
                if config.use_hvac_off_for_low_temp:
                    # Moes Logic: Use HVAC OFF for low temps
                    if target <= frost_temp:
                        desired_hvac = "off"
                    elif should_heat is not None:
                        desired_hvac = "heat" if should_heat else "off"
                    else:
                        desired_hvac = "heat"
                else:
                    # Standard TRVs: Set mode based on heating decision
                    desired_hvac = "heat" if should_heat else "off"
                
                # Apply HVAC mode if changed
                if current_hvac != desired_hvac:
                    _LOGGER.info(
                        "TRV %s: Setting HVAC mode %s -> %s",
                        trv_id, current_hvac, desired_hvac
                    )
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {"entity_id": trv_id, "hvac_mode": desired_hvac},
                        blocking=False,
                        context=self._last_command_context,
                    )
                
                # Apply temperature (Always apply target, even in OFF mode for safety)
                # Why? Some TRVs don't fully close in OFF mode, or user might have a dumb TRV
                # where we simulate OFF by setting low temp. Also ensures display matches reality.
                if True:
                    # Get calibrated target with offset compensation
                    calibrated = target
                    
                    # Get room temp from coordinator
                    room_temp = self.coordinator.get_current_temperature()
                    
                    # Get TRV's internal sensor temp
                    trv_temp = state.attributes.get("current_temperature")
                    if trv_temp is not None:
                        try:
                            trv_temp = float(trv_temp)
                        except (ValueError, TypeError):
                            trv_temp = None
                    
                    # Apply calibration if we have both sensors and calibration_manager
                    if room_temp and trv_temp and hasattr(self.coordinator, 'calibration_manager'):
                        calibrated = self.coordinator.calibration_manager.get_calibrated_target(
                            trv_id, target, room_temp, trv_temp,
                            max_temp=config.max_temp if hasattr(config, 'max_temp') else 30.0
                        )
                        if abs(calibrated - target) > 0.1:
                            _LOGGER.info(
                                "TRV %s: Calibrated %.1f -> %.1f (room=%.1f, trv=%.1f)",
                                trv_id, target, calibrated, room_temp, trv_temp
                            )
                    
                    if current_temp is None or abs(float(current_temp) - calibrated) > 0.1:
                        _LOGGER.info(
                            "TRV %s: Setting temperature %.1f -> %.1f",
                            trv_id, float(current_temp) if current_temp else 0, calibrated
                        )
                        await self.hass.services.async_call(
                            "climate",
                            "set_temperature",
                            {"entity_id": trv_id, "temperature": calibrated},
                            blocking=False,
                            context=self._last_command_context,
                        )

                # Track what we commanded (using the FINAL CALIBRATED value)
                self._last_commanded[trv_id] = {
                    "hvac_mode": desired_hvac,
                    "temperature": calibrated,
                    "timestamp": self._last_command_time,
                }
                        
            except Exception as err:
                _LOGGER.error("Failed to apply target to TRV %s: %s", trv_id, err)

    def check_drift(self, trv_id: str, current_temp: float | None, current_mode: str) -> bool:
        """Check if TRV has drifted from our last command.
        
        Returns True if TRV state differs significantly from what we commanded.
        """
        last = self._last_commanded.get(trv_id)
        if not last:
            return False
        
        # Check mode drift
        if last["hvac_mode"] != current_mode:
            _LOGGER.debug(
                "TRV %s: Mode drift detected - commanded %s, actual %s",
                trv_id, last["hvac_mode"], current_mode
            )
            return True
        
        # Check temperature drift (only if we commanded heat mode)
        if last["hvac_mode"] == "heat" and last["temperature"] is not None:
            if current_temp is not None and abs(current_temp - last["temperature"]) > 0.5:
                _LOGGER.debug(
                    "TRV %s: Temp drift detected - commanded %.1f, actual %.1f",
                    trv_id, last["temperature"], current_temp
                )
                return True
        
        return False
