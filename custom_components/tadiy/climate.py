"""Climate platform for TaDIY."""
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

from .const import (
    ATTR_HEATING_ACTIVE,
    ATTR_HEATING_BLOCKED,
    ATTR_HEATING_RATE,
    ATTR_LEARNING_SAMPLES,
    ATTR_LAST_LEARNING_UPDATE,
    ATTR_LEARN_HEATING_RATE,
    ATTR_USE_EARLY_START,
    ATTR_WINDOW_REASON,
    DOMAIN,
    MANUFACTURER,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    MODEL_NAME,
)
from .coordinator import TaDIYDataUpdateCoordinator
from .models.room import RoomData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY climate entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TaDIYDataUpdateCoordinator = data["coordinator"]
    version: str = data["version"]

    entities = []
    for room in coordinator.rooms:
        entities.append(TaDIYClimate(coordinator, entry.entry_id, room.name, version))

    async_add_entities(entities)
    _LOGGER.info("TaDIY climate platform setup complete (%d rooms)", len(entities))


class TaDIYClimate(CoordinatorEntity[TaDIYDataUpdateCoordinator], ClimateEntity):
    """TaDIY Climate Entity - Intelligent TRV Manager."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp = MIN_TARGET_TEMP
    _attr_max_temp = MAX_TARGET_TEMP
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
        version: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_unique_id = f"{entry_id}_{room_name.lower().replace(' ', '_')}_climate"
        self._attr_name = room_name
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
            "sw_version": version,
        }
        
        _LOGGER.debug("TaDIY Climate created: %s", self._attr_name)

    @property
    def room_data(self) -> RoomData | None:
        """Get current room data from coordinator."""
        return self.coordinator.data.get(self._room_name)

    @property
    def room_config(self):
        """Get room configuration."""
        for room in self.coordinator.rooms:
            if room.name == self._room_name:
                return room
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature (fused from sensors)."""
        if room_data := self.room_data:
            return room_data.current_temperature
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if room_data := self.room_data:
            return room_data.target_temperature
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if room_data := self.room_data:
            return HVACMode.HEAT if room_data.hvac_mode == "heat" else HVACMode.OFF
        return HVACMode.OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not (room_data := self.room_data):
            return {}

        attrs = {
            "main_sensor_temperature": room_data.main_sensor_temperature,
            "trv_temperatures": room_data.trv_temperatures,
            "window_open": room_data.window_state.is_open,
            ATTR_WINDOW_REASON: room_data.window_state.reason,
            ATTR_HEATING_BLOCKED: room_data.is_heating_blocked,
            ATTR_HEATING_ACTIVE: room_data.heating_active,
            ATTR_HEATING_RATE: f"{room_data.heating_rate:.2f} °C/h",
        }

        if room_data.outdoor_temperature is not None:
            attrs["outdoor_temperature"] = room_data.outdoor_temperature

        if room_config := self.room_config:
            attrs["trv_entities"] = room_config.trv_entity_ids
            attrs["window_sensors"] = room_config.window_sensor_ids
            attrs[ATTR_USE_EARLY_START] = room_config.use_early_start
            attrs[ATTR_LEARN_HEATING_RATE] = room_config.learn_heating_rate
            
            heat_model = self.coordinator._heat_models.get(self._room_name)
            if heat_model:
                attrs[ATTR_LEARNING_SAMPLES] = heat_model.sample_count
                attrs[ATTR_LAST_LEARNING_UPDATE] = (
                    heat_model.last_updated.isoformat()
                    if heat_model.last_updated
                    else None
                )

        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.room_data is not None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        room_config = self.room_config
        if not room_config:
            _LOGGER.error("Room config not found for %s", self._room_name)
            return

        for trv_entity in room_config.trv_entity_ids:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": trv_entity,
                    "temperature": temperature,
                },
                blocking=False,
            )

        _LOGGER.info("%s: Target temperature set to %.1f°C", self._attr_name, temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        room_config = self.room_config
        if not room_config:
            _LOGGER.error("Room config not found for %s", self._room_name)
            return

        ha_hvac_mode = "heat" if hvac_mode == HVACMode.HEAT else "off"
        
        for trv_entity in room_config.trv_entity_ids:
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {
                    "entity_id": trv_entity,
                    "hvac_mode": ha_hvac_mode,
                },
                blocking=False,
            )

        _LOGGER.info("%s: HVAC mode set to %s", self._attr_name, hvac_mode)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
