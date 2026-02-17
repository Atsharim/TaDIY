"""Climate platform for TaDIY integration."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY climate entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_type = entry_data.get("type")

    if entry_type == "hub":
        _LOGGER.debug("Hub entry - no climate entities")
        return

    if entry_type == "room":
        coordinator = entry_data["coordinator"]
        room_name = coordinator.room_config.name
        trv_entities = coordinator.room_config.trv_entity_ids

        # Create ONE unified climate entity per room that controls all TRVs
        entities = [TaDIYClimateEntity(coordinator, room_name, trv_entities, entry)]

        async_add_entities(entities)
        _LOGGER.info(
            "Added unified climate entity for room: %s (controlling %d TRVs)",
            room_name,
            len(trv_entities),
        )


class TaDIYClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a TaDIY Climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, coordinator, room_name: str, trv_entity_ids: list[str], entry: ConfigEntry
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._trv_entity_ids = trv_entity_ids
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_has_entity_name = True  # Use device name as entity name
        self._attr_name = None  # No additional name suffix
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        # Use commanded target first (most up-to-date)
        if self.coordinator._commanded_target is not None:
            return self.coordinator._commanded_target
        # Fallback to coordinator data
        if self.coordinator.data:
            return self.coordinator.data.target_temperature
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        # Use commanded mode first
        commanded = getattr(self.coordinator, "_commanded_hvac_mode", None)
        if commanded:
            return HVACMode.HEAT if commanded == "heat" else HVACMode.OFF
        # Fallback to coordinator data
        if self.coordinator.data:
            return HVACMode.HEAT if self.coordinator.data.hvac_mode == "heat" else HVACMode.OFF
        return HVACMode.OFF

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 5.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30.0

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "integration": "tadiy",
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for all TRVs in this room."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        _LOGGER.info(
            "Room %s: User requested temperature %.1f°C",
            self._room_name,
            temperature,
        )

        # Notify coordinator of user interaction for grace period
        self.coordinator.notify_user_interaction()

        # Create override to prevent schedule from overwriting user's choice
        # We always create an override if the target differs from schedule 
        # OR if we are in manual mode (to ensure the manual choice is remembered)
        scheduled_target = self.coordinator.get_scheduled_target()
        hub_mode = self.coordinator.get_hub_mode()
        
        # If no scheduled target (manual mode), we still want to store this as an override
        # to ensure it's preserved through restarts and update cycles
        should_create_override = False
        if scheduled_target is None:
            should_create_override = True
        elif abs(temperature - scheduled_target) > 0.1:
            should_create_override = True
        elif hub_mode == "manual":
            should_create_override = True

        if should_create_override:
            timeout_mode = self.coordinator.get_override_timeout()
            next_change = self.coordinator.schedule_engine.get_next_schedule_change(
                self.coordinator.room_config.name, hub_mode
            )
            next_block_time = next_change[0] if next_change else None

            # Create override for the room (using first TRV as reference)
            for trv_entity_id in self._trv_entity_ids:
                self.coordinator.override_manager.create_override(
                    entity_id=trv_entity_id,
                    scheduled_temp=scheduled_target or 20.0,
                    override_temp=temperature,
                    timeout_mode=timeout_mode,
                    next_block_time=next_block_time,
                )
            self.hass.async_create_task(self.coordinator.async_save_overrides())
            _LOGGER.info(
                "Room %s: Created/Updated override for %.1f°C (scheduled was %s)",
                self._room_name,
                temperature,
                scheduled_target if scheduled_target is not None else "None (Manual Mode)",
            )

        # Get current room temperature for auto-calibration
        room_temp = (
            self.coordinator.current_room_data.current_temperature
            if self.coordinator.current_room_data
            else None
        )

        # Set temperature for all TRVs in the room (with calibration)
        for trv_entity_id in self._trv_entity_ids:
            try:
                # Get TRV current temperature
                trv_state = self.hass.states.get(trv_entity_id)
                trv_temp = None
                if trv_state:
                    trv_current = trv_state.attributes.get("current_temperature")
                    if trv_current:
                        try:
                            trv_temp = float(trv_current)
                        except (ValueError, TypeError):
                            pass

                # Update auto-calibration if applicable
                if room_temp and trv_temp:
                    self.coordinator.calibration_manager.update_auto_calibration(
                        trv_entity_id, trv_temp, room_temp
                    )

                # Get calibrated target
                calibrated_temp = (
                    self.coordinator.calibration_manager.get_calibrated_target(
                        trv_entity_id, temperature, room_temp, trv_temp
                    )
                )

                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": trv_entity_id, "temperature": calibrated_temp},
                    blocking=True,
                )

                # Update last known target to prevent re-detection as manual change
                self.coordinator._last_trv_targets[trv_entity_id] = calibrated_temp

                # Log calibration info
                cal_info = self.coordinator.calibration_manager.get_calibration_info(
                    trv_entity_id
                )
                if cal_info and cal_info["mode"] != "disabled":
                    _LOGGER.debug(
                        "TRV %s: Set target %.1f°C (calibrated from %.1f°C, mode=%s)",
                        trv_entity_id,
                        calibrated_temp,
                        temperature,
                        cal_info["mode"],
                    )
                else:
                    _LOGGER.debug(
                        "TRV %s: Set target %.1f°C (no calibration)",
                        trv_entity_id,
                        temperature,
                    )

            except Exception as err:
                _LOGGER.error(
                    "Failed to set temperature for %s: %s", trv_entity_id, err
                )

        # Immediately update commanded target to reflect user's choice
        # This prevents bouncing while waiting for next update cycle
        self.coordinator._commanded_target = temperature
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode for all TRVs in this room."""
        # Notify coordinator of user interaction for grace period
        self.coordinator.notify_user_interaction()
        # Set HVAC mode for all TRVs in the room
        for trv_entity_id in self._trv_entity_ids:
            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": trv_entity_id, "hvac_mode": hvac_mode},
                    blocking=True,
                )
            except Exception as err:
                _LOGGER.error("Failed to set HVAC mode for %s: %s", trv_entity_id, err)

        # Update commanded mode (convert enum to string) and refresh state
        self.coordinator._commanded_hvac_mode = "heat" if hvac_mode == HVACMode.HEAT else "off"
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
