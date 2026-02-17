"""TRV management logic for TaDIY."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__package__)

class TrvManager:
    """Handles communication with TRV devices for a room."""

    def __init__(self, coordinator: Any) -> None:
        """Initialize the TRV manager."""
        self.coordinator = coordinator
        self.hass = coordinator.hass

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
        """Apply target temperature and HVAC mode to all TRVs."""
        config = self.coordinator.room_config
        frost_temp = self.coordinator.hub_coordinator.get_frost_protection_temp() if self.coordinator.hub_coordinator else 5.0

        for trv_id in config.trv_entity_ids:
            try:
                state = self.hass.states.get(trv_id)
                if not state:
                    continue

                current_hvac = state.state
                current_temp = state.attributes.get("temperature")
                
                # Moes Logic: Scale mode based on heating decision
                if config.use_hvac_off_for_low_temp:
                    # Determine desired HVAC mode
                    if target <= frost_temp:
                        desired_hvac = "off"
                    elif should_heat is not None:
                        desired_hvac = "heat" if should_heat else "off"
                    else:
                        desired_hvac = "heat" # Default to heat if no specific decision
                        
                    # Apply HVAC mode if changed
                    if current_hvac != desired_hvac:
                         await self.hass.services.async_call(
                            "climate",
                            "set_hvac_mode",
                            {"entity_id": trv_id, "hvac_mode": desired_hvac},
                            blocking=False,
                        )
                    
                    # Apply temperature if in heat mode
                    if desired_hvac == "heat":
                        if current_temp is None or abs(float(current_temp) - target) > 0.1:
                            await self.hass.services.async_call(
                                "climate",
                                "set_temperature",
                                {"entity_id": trv_id, "temperature": target},
                                blocking=False,
                            )
                else:
                    # Standard TRVs: Always in heat mode, just set temperature
                    if current_temp is None or abs(float(current_temp) - target) > 0.1:
                         await self.hass.services.async_call(
                            "climate",
                            "set_temperature",
                            {"entity_id": trv_id, "temperature": target},
                            blocking=False,
                        )
            except Exception as err:
                _LOGGER.error("Failed to apply target to TRV %s: %s", trv_id, err)
