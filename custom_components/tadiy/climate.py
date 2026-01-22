"""Climate platform for TaDIY integration."""
from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
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
        _LOGGER.info("Added unified climate entity for room: %s (controlling %d TRVs)", room_name, len(trv_entities))


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

    def __init__(self, coordinator, room_name: str, trv_entity_ids: list[str], entry: ConfigEntry) -> None:
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
        if not self.coordinator.data:
            return None
        return self.coordinator.data.target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        if not self.coordinator.data:
            return HVACMode.OFF
        return HVACMode.HEAT if self.coordinator.data.hvac_mode == "heat" else HVACMode.OFF

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
                calibrated_temp = self.coordinator.calibration_manager.get_calibrated_target(
                    trv_entity_id, temperature, room_temp, trv_temp
                )

                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": trv_entity_id, "temperature": calibrated_temp},
                    blocking=True,
                )

                # Log calibration info
                cal_info = self.coordinator.calibration_manager.get_calibration_info(
                    trv_entity_id
                )
                if cal_info and cal_info["mode"] != "disabled":
                    _LOGGER.debug(
                        "TRV %s: Set target %.1f°C (calibrated from %.1f°C, mode=%s, multiplier=%.3f)",
                        trv_entity_id,
                        calibrated_temp,
                        temperature,
                        cal_info["mode"],
                        cal_info["multiplier"] if cal_info["mode"] == "auto" else 1.0,
                    )
                else:
                    _LOGGER.debug(
                        "TRV %s: Set target %.1f°C (no calibration)",
                        trv_entity_id,
                        temperature,
                    )

            except Exception as err:
                _LOGGER.error("Failed to set temperature for %s: %s", trv_entity_id, err)

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode for all TRVs in this room."""
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

        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()