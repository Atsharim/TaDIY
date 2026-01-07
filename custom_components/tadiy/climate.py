"""Climate platform for TaDIY."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_TADIY_MODE,
    ATTR_TADIY_OVERRIDE_ACTIVE,
    ATTR_TADIY_OVERRIDE_UNTIL,
    ATTR_TADIY_SCHEDULE_ACTIVE,
    ATTR_TADIY_SCHEDULED_TARGET,
    DOMAIN,
    ICON_HEATING,
    MANUFACTURER,
    MAX_TARGET_TEMP,
    MIN_TARGET_TEMP,
    MODE_MANUAL,
    MODE_OFF,
    MODEL_NAME,
)
from .coordinator import TaDIYDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY climate entities."""
    coordinator: TaDIYDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    entities = []
    for room in coordinator.rooms:
        entities.append(
            TaDIYClimateEntity(
                coordinator,
                config_entry.entry_id,
                room.name,
            )
        )

    async_add_entities(entities)
    _LOGGER.info("TaDIY climate platform setup complete with %d entities", len(entities))


class TaDIYClimateEntity(CoordinatorEntity, ClimateEntity):
    """TaDIY Climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_icon = ICON_HEATING
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = room_name
        self._attr_unique_id = f"{entry_id}_{room_name}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

        # Get room config
        self._room_config = None
        for room in coordinator.rooms:
            if room.name == room_name:
                self._room_config = room
                break

        # Temperature bounds
        self._attr_min_temp = MIN_TARGET_TEMP
        self._attr_max_temp = MAX_TARGET_TEMP
        self._attr_target_temperature_step = 0.5

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if not self.coordinator.data:
            return None

        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return None

        # Use fused temperature
        return room_data.get("fused_temp")

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        mode = self.coordinator.get_hub_mode()
        
        # OFF mode: Return frost protection
        if mode == MODE_OFF:
            return self.coordinator.get_frost_protection_temp()
        
        # MANUAL mode: Get from TRVs (first available)
        if mode == MODE_MANUAL:
            return self._get_trv_target()
        
        # NORMAL/HOMEOFFICE: Get scheduled target
        scheduled = self.coordinator.get_scheduled_target(self._room_name)
        if scheduled is not None:
            return scheduled
        
        # Fallback: Get from TRVs
        return self._get_trv_target()

    def _get_trv_target(self) -> float | None:
        """Get target temperature from first available TRV."""
        if not self._room_config:
            return None

        for trv_id in self._room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_id)
            if trv_state and trv_state.attributes.get(ATTR_TEMPERATURE):
                try:
                    return float(trv_state.attributes[ATTR_TEMPERATURE])
                except (ValueError, TypeError):
                    pass
        
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        mode = self.coordinator.get_hub_mode()
        
        if mode == MODE_OFF:
            return HVACMode.OFF
        
        # Check if any TRV is heating
        if self._room_config:
            for trv_id in self._room_config.trv_entity_ids:
                trv_state = self.hass.states.get(trv_id)
                if trv_state:
                    hvac_action = trv_state.attributes.get("hvac_action")
                    if hvac_action == "heating":
                        return HVACMode.HEAT
        
        return HVACMode.HEAT

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        # Hub mode
        mode = self.coordinator.get_hub_mode()
        attrs[ATTR_TADIY_MODE] = mode
        
        # Scheduled target
        scheduled_target = self.coordinator.get_scheduled_target(self._room_name)
        attrs[ATTR_TADIY_SCHEDULED_TARGET] = scheduled_target
        
        # Schedule active?
        attrs[ATTR_TADIY_SCHEDULE_ACTIVE] = (
            scheduled_target is not None and mode not in (MODE_MANUAL, MODE_OFF)
        )
        
        # Override detection
        if scheduled_target is not None:
            current_target = self._get_trv_target()
            if current_target is not None:
                override_info = self.coordinator.check_override(
                    self._room_name, current_target, scheduled_target
                )
                attrs[ATTR_TADIY_OVERRIDE_ACTIVE] = override_info["is_override"]
                attrs[ATTR_TADIY_OVERRIDE_UNTIL] = (
                    override_info["override_until"].isoformat()
                    if override_info["override_until"]
                    else None
                )
            else:
                attrs[ATTR_TADIY_OVERRIDE_ACTIVE] = False
                attrs[ATTR_TADIY_OVERRIDE_UNTIL] = None
        else:
            attrs[ATTR_TADIY_OVERRIDE_ACTIVE] = False
            attrs[ATTR_TADIY_OVERRIDE_UNTIL] = None
        
        # Room data
        if self.coordinator.data:
            room_data = self.coordinator.data.get(self._room_name)
            if room_data:
                attrs["main_temperature"] = room_data.get("main_temp")
                attrs["outdoor_temperature"] = room_data.get("outdoor_temp")
                attrs["window_open"] = room_data.get("window_open")
                
                # Heating rate
                if room_data.get("heating_rate"):
                    attrs["heating_rate"] = room_data["heating_rate"]
        
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if not self._room_config:
            _LOGGER.error("Room config not found for %s", self._room_name)
            return

        mode = self.coordinator.get_hub_mode()
        
        _LOGGER.info(
            "Setting temperature for room %s to %.1f°C (mode: %s)",
            self._room_name,
            temperature,
            mode,
        )

        # Set temperature on all TRVs
        for trv_id in self._room_config.trv_entity_ids:
            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": trv_id,
                        "temperature": temperature,
                    },
                    blocking=True,
                )
                _LOGGER.debug("Temperature set for TRV: %s", trv_id)
            except Exception as err:
                _LOGGER.error("Failed to set temperature on %s: %s", trv_id, err)

        # Trigger override check
        scheduled = self.coordinator.get_scheduled_target(self._room_name)
        if scheduled is not None:
            self.coordinator.check_override(self._room_name, temperature, scheduled)

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self._room_config:
            return

        _LOGGER.info(
            "Setting HVAC mode for room %s to %s",
            self._room_name,
            hvac_mode,
        )

        # Set mode on all TRVs
        for trv_id in self._room_config.trv_entity_ids:
            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {
                        "entity_id": trv_id,
                        "hvac_mode": hvac_mode.value,
                    },
                    blocking=True,
                )
            except Exception as err:
                _LOGGER.error("Failed to set HVAC mode on %s: %s", trv_id, err)

        await self.coordinator.async_request_refresh()
