"""Climate platform for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OVERRIDE_TIMEOUT_NEVER
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
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
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
        self._entry = entry
        self._room_name = room_name
        self._trv_entity_ids = trv_entity_ids
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_has_entity_name = True  # Use device name as entity name
        self._attr_name = None  # No additional name suffix
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.current_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature for older HA versions."""
        return self.native_current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        # Use commanded target first (most up-to-date)
        if self.coordinator._commanded_target is not None:
            return self.coordinator._commanded_target
        # Fallback to coordinator data
        if self.coordinator.data:
            return self.coordinator.data.target_temperature
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature for older HA versions."""
        return self.native_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        if getattr(self.coordinator, "_manual_room_off", False):
            return HVACMode.OFF
        if (
            hasattr(self.coordinator, "get_hub_mode")
            and self.coordinator.get_hub_mode() == "off"
        ):
            return HVACMode.OFF
        if (
            self.coordinator.data
            and getattr(self.coordinator.data, "window_state", None)
            and self.coordinator.data.window_state.heating_should_stop
        ):
            return HVACMode.OFF

        commanded = getattr(self.coordinator, "_commanded_hvac_mode", None)
        if commanded:
            return HVACMode.HEAT if commanded == "heat" else HVACMode.OFF

        if self.coordinator.data:
            return (
                HVACMode.HEAT
                if self.coordinator.data.hvac_mode == "heat"
                else HVACMode.OFF
            )
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.coordinator.data and self.coordinator.data.heating_active:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 5.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30.0

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        if (
            self.coordinator
            and self.coordinator.data
            and self.coordinator.data.humidity is not None
        ):
            return round(self.coordinator.data.humidity, 1)
        return None

    @property
    def native_target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if self.coordinator and hasattr(self.coordinator, "room_config"):
            return self.coordinator.room_config.target_temp_step
        return 0.5

    @property
    def target_temperature_step(self) -> float:
        """Return target temperature step for older HA versions."""
        return self.native_target_temperature_step

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs: dict[str, Any] = {
            "integration": "tadiy",
            "room_name": self._room_name,
            "entry_id": self._entry.entry_id,
            "trv_entities": list(self._trv_entity_ids or []),
        }
        if self.coordinator and self.coordinator.data:
            data = self.coordinator.data
            if data.current_temperature is not None:
                from .core.temperature import calculate_comfort

                try:
                    comfort = calculate_comfort(
                        data.current_temperature,
                        data.humidity,
                    )
                    attrs["comfort_score"] = comfort.get("comfort_score")
                    attrs["comfort_level"] = comfort.get("comfort_level")
                    attrs["comfort_color"] = comfort.get("comfort_color")
                except Exception:
                    pass

            attrs["target_source"] = getattr(data, "target_source", None)
            attrs["decision_reason"] = getattr(data, "decision_reason", None)
            attrs["decision_time"] = (
                data.decision_time.isoformat()
                if getattr(data, "decision_time", None)
                else None
            )
            attrs["active_temp_sensor"] = getattr(data, "active_temp_sensor", None)
            attrs["sensor_fallback_active"] = getattr(data, "sensor_fallback_active", False)
            attrs["heating_rate"] = getattr(data, "heating_rate", None)
            attrs["heating_rate_samples"] = getattr(data, "heating_rate_sample_count", 0)
            attrs["heating_rate_confidence"] = getattr(data, "heating_rate_confidence", 0.0)
            attrs["heating_rate_last_updated"] = (
                data.heating_rate_last_updated.isoformat()
                if getattr(data, "heating_rate_last_updated", None)
                else None
            )
            attrs["override_active"] = getattr(data, "override_active", False)

            # TRV target exposure for panel diagnosis
            trv_target = None
            if hasattr(self.coordinator, "_last_trv_targets") and self.coordinator._last_trv_targets:
                trv_targets = [t for t in self.coordinator._last_trv_targets.values() if t is not None]
                if trv_targets:
                    trv_target = round(sum(trv_targets) / len(trv_targets), 1)
            attrs["trv_target_temperature"] = trv_target
            attrs["trv_target"] = trv_target

        if self.coordinator and hasattr(self.coordinator, "room_config"):
            cfg = self.coordinator.room_config
            opts = self._entry.options if self._entry else {}
            attrs["away_temperature"] = getattr(cfg, "away_temperature", opts.get("away_temperature", 15.0))
            attrs["tolerance"] = getattr(cfg, "tolerance", opts.get("tolerance", 0.5))
            attrs["early_start_max_minutes"] = getattr(cfg, "early_start_max_minutes", opts.get("early_start_max_minutes", 120))
            attrs["window_open_timeout"] = getattr(cfg, "window_open_timeout", opts.get("window_open_timeout", 30))
            attrs["window_close_timeout"] = getattr(cfg, "window_close_timeout", opts.get("window_close_timeout", 60))
            attrs["min_heating_rate"] = getattr(cfg, "min_heating_rate", opts.get("min_heating_rate", 0.5))
            attrs["max_heating_rate"] = getattr(cfg, "max_heating_rate", opts.get("max_heating_rate", 3.0))
            attrs["dont_heat_below_outdoor"] = getattr(cfg, "dont_heat_below_outdoor", opts.get("dont_heat_below_outdoor"))
            attrs["adjacent_rooms"] = getattr(cfg, "adjacent_rooms", opts.get("adjacent_rooms", []))

        return attrs

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

        # Setting temperature clears manual room off
        if (
            hasattr(self.coordinator, "is_manual_room_off")
            and self.coordinator.is_manual_room_off()
        ):
            self.coordinator.set_manual_room_off(False)

        # Unified override logic: same as hardware changes
        hub_mode = self.coordinator.get_hub_mode()

        # Determine reference value and timeout based on mode
        if hub_mode == "off":
            # Off mode: 2h temporary override
            reference_target = (
                self.coordinator.hub_coordinator.get_frost_protection_temp()
                if self.coordinator.hub_coordinator
                else 5.0
            )
            override_timeout = "2h"
            next_block_time = None
        elif hub_mode == "manual":
            # Manual mode: permanent override
            reference_target = self.coordinator._commanded_target or 20.0
            override_timeout = OVERRIDE_TIMEOUT_NEVER
            next_block_time = None
        else:
            # Schedule mode: use scheduled target and configured timeout
            reference_target = self.coordinator.get_scheduled_target() or 20.0
            override_timeout = self.coordinator.get_override_timeout()
            next_change = self.coordinator.schedule_engine.get_next_schedule_change(
                self.coordinator.room_config.name, hub_mode
            )
            next_block_time = next_change[0] if next_change else None

        # Create override for all TRVs in the room
        for trv_entity_id in self._trv_entity_ids:
            self.coordinator.override_manager.create_override(
                entity_id=trv_entity_id,
                scheduled_temp=reference_target,
                override_temp=temperature,
                timeout_mode=override_timeout,
                next_block_time=next_block_time,
            )
        self.hass.async_create_task(self.coordinator.async_save_overrides())
        _LOGGER.info(
            "Room %s: Created override in %s mode (reference=%.1f, target=%.1f, timeout=%s)",
            self._room_name,
            hub_mode,
            reference_target,
            temperature,
            override_timeout,
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
                    self.coordinator.calibration_manager.update_calibration(
                        trv_entity_id, trv_temp, room_temp
                    )

                # Get calibrated target with offset compensation
                calibrated_temp = (
                    self.coordinator.calibration_manager.get_calibrated_target(
                        trv_entity_id,
                        temperature,
                        room_temp,
                        trv_temp,
                        max_temp=self.max_temp,
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

    async def async_turn_off(self) -> None:
        """Turn off the climate entity."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn on the climate entity."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode for all TRVs in this room."""
        # Notify coordinator of user interaction for grace period
        self.coordinator.notify_user_interaction()
        if hasattr(self.coordinator, "set_manual_room_off"):
            self.coordinator.set_manual_room_off(hvac_mode == HVACMode.OFF)
        else:
            self.coordinator._commanded_hvac_mode = (
                "heat" if hvac_mode == HVACMode.HEAT else "off"
            )

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

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
