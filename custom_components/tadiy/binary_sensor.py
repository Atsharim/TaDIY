"""Binary sensor platform for TaDIY integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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
    """Set up TaDIY binary sensor entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[BinarySensorEntity] = []

    if entry_type == "room":
        entities.append(TaDIYRoomHeatingProblemBinarySensor(coordinator, entry))
        entities.append(TaDIYRoomWindowBinarySensor(coordinator, entry))
        _LOGGER.info(
            "Added binary sensors (problem, window) for room %s",
            coordinator.room_config.name,
        )
    elif entry_type == "hub":
        if getattr(coordinator, "boiler_temp_sensor", None):
            entities.append(TaDIYHubBoilerBinarySensor(coordinator, entry))
            _LOGGER.info("Added boiler active binary sensor for hub")

    async_add_entities(entities)


class TaDIYRoomHeatingProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Problem binary sensor for heating failure and stuck valves in a room."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the problem sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_heating_problem"
        self._attr_translation_key = "heating_problem"
        self._attr_name = "Heating Problem"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def is_on(self) -> bool:
        """Return True if a heating problem is detected in this room."""
        if hasattr(self.coordinator, "safety_manager"):
            return self.coordinator.safety_manager.state.any_alert
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details about active problem."""
        if not hasattr(self.coordinator, "safety_manager"):
            return {}

        state = self.coordinator.safety_manager.state
        return {
            "problem_type": state.active_problem_type,
            "problem_description": state.active_problem_description,
            "problem_since": (
                state.active_problem_since.isoformat()
                if state.active_problem_since
                else None
            ),
            "valve_stuck_open": state.valve_stuck_open,
            "heating_failure": state.heating_failure,
            "overheat": state.overheat_active,
            "frost": state.frost_active,
            "active_alerts": self.coordinator.safety_manager.get_active_alerts(),
            "room_name": self.coordinator.room_config.name,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYRoomWindowBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Window binary sensor for open window detection in a room."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the window binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_window"
        self._attr_translation_key = "window"
        self._attr_name = "Window"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def is_on(self) -> bool:
        """Return True if any window in this room is open."""
        data = getattr(self.coordinator, "data", None)
        ws = getattr(data, "window_state", None) if data else None
        if ws is not None:
            return bool(ws.is_open)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return window state attributes."""
        data = getattr(self.coordinator, "data", None)
        ws = getattr(data, "window_state", None) if data else None
        if not ws:
            return {}
        return {
            "heating_should_stop": ws.heating_should_stop,
            "timeout_active": ws.timeout_active,
            "timeout_ends_at": (
                ws.timeout_ends_at.isoformat() if ws.timeout_ends_at else None
            ),
            "reason": ws.reason,
            "detection_method": (
                "contact_sensor"
                if getattr(self.coordinator.room_config, "window_sensor_ids", None)
                else "temperature_drop"
            ),
            "room_name": self.coordinator.room_config.name,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYHubBoilerBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating active hot water supply flow in the boiler."""

    _attr_has_entity_name = True
    _attr_device_class = getattr(BinarySensorDeviceClass, "HEAT", "heat")
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the boiler binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_boiler_active"
        self._attr_translation_key = "boiler_active"
        self._attr_name = "Heißwasser aktiv"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def is_on(self) -> bool:
        """Return True if the boiler is actively delivering heat (>= 45°C)."""
        data = getattr(self.coordinator, "data", None)
        if data:
            return bool(data.get("boiler_active", False))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return boiler attributes."""
        data = getattr(self.coordinator, "data", None)
        if not data:
            return {}
        return {
            "boiler_temperature": data.get("boiler_temperature"),
            "sensor_available": data.get("boiler_sensor_available", True),
            "source_sensor": data.get("boiler_temp_sensor_id"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

