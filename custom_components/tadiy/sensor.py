"""Sensor platform for TaDIY integration."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_TEMPERATURE, ICON_LEARNING, ICON_MODE
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass
class TaDIYSensorEntityDescription(SensorEntityDescription):
    """Describes TaDIY sensor entity."""
    value_fn: Callable[[Any], Any] | None = None
    available_fn: Callable[[Any], bool] | None = None
    attr_fn: Callable[[Any], dict[str, Any]] | None = None


ROOM_SENSOR_TYPES: tuple[TaDIYSensorEntityDescription, ...] = (
    TaDIYSensorEntityDescription(
        key="current_temperature",
        name="Current Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: data.current_temperature if data else None,
        available_fn=lambda data: data is not None and data.current_temperature is not None,
    ),
    TaDIYSensorEntityDescription(
        key="target_temperature",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: data.target_temperature if data else None,
        available_fn=lambda data: data is not None and data.target_temperature is not None,
    ),
    TaDIYSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: round(data.humidity, 1) if data and data.humidity is not None else None,
        available_fn=lambda data: data is not None and data.humidity is not None,
    ),
    TaDIYSensorEntityDescription(
        key="heating_rate",
        name="Heating Rate",
        native_unit_of_measurement="°C/h",
        icon=ICON_LEARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: round(data.heating_rate, 2) if data and data.heating_rate else None,
        available_fn=lambda data: data is not None and data.heating_rate is not None,
        attr_fn=lambda data: {
            "sample_count": data.heating_rate_sample_count if hasattr(data, "heating_rate_sample_count") else 0,
            "confidence": round(data.heating_rate_confidence, 2) if hasattr(data, "heating_rate_confidence") else 0.0,
        } if data else {},
    ),
    TaDIYSensorEntityDescription(
        key="main_sensor_temperature",
        name="Main Sensor Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: round(data.main_sensor_temperature, 2) if data and data.main_sensor_temperature else None,
        available_fn=lambda data: data is not None and data.main_sensor_temperature is not None,
    ),
    TaDIYSensorEntityDescription(
        key="trv_temperatures",
        name="TRV Temperatures",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: round(sum(data.trv_temperatures) / len(data.trv_temperatures), 2) if data and data.trv_temperatures else None,
        available_fn=lambda data: data is not None and data.trv_temperatures,
        attr_fn=lambda data: {
            "trv_count": len(data.trv_temperatures) if data and data.trv_temperatures else 0,
            "trv_values": [round(t, 2) for t in data.trv_temperatures] if data and data.trv_temperatures else [],
            "min_trv_temp": round(min(data.trv_temperatures), 2) if data and data.trv_temperatures else None,
            "max_trv_temp": round(max(data.trv_temperatures), 2) if data and data.trv_temperatures else None,
        } if data else {},
    ),
    TaDIYSensorEntityDescription(
        key="override_status",
        name="Override Status",
        icon="mdi:thermometer-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: "Active" if data and data.override_active else "None",
        available_fn=lambda data: data is not None,
        attr_fn=lambda data: {
            "override_count": data.override_count if hasattr(data, "override_count") else 0,
        } if data else {},
    ),
)

HUB_SENSOR_TYPES: tuple[TaDIYSensorEntityDescription, ...] = (
    TaDIYSensorEntityDescription(
        key="hub_mode",
        name="Hub Mode",
        icon=ICON_MODE,
        value_fn=lambda data: data.get("hub_mode", "unknown") if data else "unknown",
    ),
    TaDIYSensorEntityDescription(
        key="location_status",
        name="Location Status",
        icon="mdi:home-account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("location_status", "unknown") if data else "unknown",
        attr_fn=lambda data: data.get("location_attributes", {}) if data else {},
    ),
    TaDIYSensorEntityDescription(
        key="weather_prediction",
        name="Weather Prediction",
        icon="mdi:weather-partly-cloudy",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("weather_prediction", {}).get("trend", "unknown") if data else "unknown",
        available_fn=lambda data: data is not None and data.get("weather_prediction", {}).get("available", False),
        attr_fn=lambda data: data.get("weather_prediction", {}) if data else {},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[SensorEntity] = []

    if entry_type == "hub":
        for description in HUB_SENSOR_TYPES:
            entities.append(TaDIYHubSensor(coordinator, description, entry))
        _LOGGER.info("Added %d hub sensor entities", len(entities))
    elif entry_type == "room":
        for description in ROOM_SENSOR_TYPES:
            entities.append(TaDIYRoomSensor(coordinator, description, entry))

        # Add TRV calibration diagnostic sensor
        entities.append(TaDIYTRVCalibrationSensor(coordinator, entry))

        # Add battery diagnostic sensors
        entities.append(TaDIYBatteryStatusSensor(coordinator, entry))

        # Add override diagnostic sensor
        entities.append(TaDIYOverrideDetailSensor(coordinator, entry))

        _LOGGER.info("Added %d room sensor entities", len(entities))

    async_add_entities(entities)


class TaDIYRoomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Room Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if self.entity_description.available_fn is not None:
            return self.entity_description.available_fn(self.coordinator.data)
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if self.entity_description.attr_fn is not None:
            return self.entity_description.attr_fn(self.coordinator.data)
        return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYHubSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Hub Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYTRVCalibrationSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for TRV calibration data."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = ICON_TEMPERATURE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_trv_calibration"
        self._attr_name = "TRV Calibration"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        cal_mgr = self.coordinator.calibration_manager
        active_calibrations = sum(
            1 for cal in cal_mgr._calibrations.values() if cal.mode != "disabled"
        )
        return f"{active_calibrations}/{len(cal_mgr._calibrations)}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        cal_mgr = self.coordinator.calibration_manager
        room_data = self.coordinator.current_room_data

        attributes = {
            "main_sensor_temp": round(room_data.main_sensor_temperature, 2) if room_data else None,
            "fused_temp": round(room_data.current_temperature, 2) if room_data else None,
            "trv_entity_ids": list(self.coordinator.room_config.trv_entity_ids),
        }

        # Add per-TRV calibration data
        for entity_id in self.coordinator.room_config.trv_entity_ids:
            trv_state = self.hass.states.get(entity_id)
            trv_temp = None
            if trv_state:
                trv_current = trv_state.attributes.get("current_temperature")
                if trv_current:
                    try:
                        trv_temp = float(trv_current)
                    except (ValueError, TypeError):
                        pass

            # Get calibration info
            cal_info = cal_mgr.get_calibration_info(entity_id)

            trv_key = entity_id.replace("climate.", "").replace(".", "_")
            if cal_info:
                attributes[f"{trv_key}_mode"] = cal_info["mode"]
                attributes[f"{trv_key}_multiplier"] = round(cal_info["multiplier"], 3)
                attributes[f"{trv_key}_offset"] = round(cal_info["offset"], 1)
                attributes[f"{trv_key}_current_temp"] = round(trv_temp, 2) if trv_temp else None
                attributes[f"{trv_key}_last_room_temp"] = (
                    round(cal_info["last_room_temp"], 2) if cal_info["last_room_temp"] else None
                )
                attributes[f"{trv_key}_last_trv_temp"] = (
                    round(cal_info["last_trv_temp"], 2) if cal_info["last_trv_temp"] else None
                )
                attributes[f"{trv_key}_last_calibrated"] = cal_info["last_calibrated"]
            else:
                # No calibration data yet
                attributes[f"{trv_key}_mode"] = "auto"
                attributes[f"{trv_key}_multiplier"] = 1.0
                attributes[f"{trv_key}_offset"] = 0.0
                attributes[f"{trv_key}_current_temp"] = round(trv_temp, 2) if trv_temp else None

        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYBatteryStatusSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for battery status of all devices in room."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery_status"
        self._attr_name = "Battery Status"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> str:
        """Return the state of the sensor (count of low batteries)."""
        low_battery_count = 0
        total_battery_count = 0

        # Check TRVs
        for entity_id in self.coordinator.room_config.trv_entity_ids:
            state = self.hass.states.get(entity_id)
            if state:
                battery = state.attributes.get("battery")
                if battery is not None:
                    total_battery_count += 1
                    try:
                        battery_level = float(battery)
                        if battery_level < 20:
                            low_battery_count += 1
                    except (ValueError, TypeError):
                        pass

        # Check main temperature sensor
        if self.coordinator.room_config.main_temp_sensor_id:
            state = self.hass.states.get(self.coordinator.room_config.main_temp_sensor_id)
            if state:
                battery = state.attributes.get("battery")
                if battery is not None:
                    total_battery_count += 1
                    try:
                        battery_level = float(battery)
                        if battery_level < 20:
                            low_battery_count += 1
                    except (ValueError, TypeError):
                        pass

        # Check humidity sensor
        if self.coordinator.room_config.humidity_sensor_id:
            state = self.hass.states.get(self.coordinator.room_config.humidity_sensor_id)
            if state:
                battery = state.attributes.get("battery")
                if battery is not None:
                    total_battery_count += 1
                    try:
                        battery_level = float(battery)
                        if battery_level < 20:
                            low_battery_count += 1
                    except (ValueError, TypeError):
                        pass

        if total_battery_count == 0:
            return "No battery devices"
        if low_battery_count == 0:
            return "All OK"
        return f"{low_battery_count}/{total_battery_count} Low"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {}

        # Check TRVs
        for entity_id in self.coordinator.room_config.trv_entity_ids:
            state = self.hass.states.get(entity_id)
            if state:
                battery = state.attributes.get("battery")
                battery_low = state.attributes.get("battery_low")

                trv_key = entity_id.replace("climate.", "").replace(".", "_")
                if battery is not None:
                    try:
                        attributes[f"{trv_key}_battery"] = float(battery)
                    except (ValueError, TypeError):
                        attributes[f"{trv_key}_battery"] = battery
                if battery_low is not None:
                    attributes[f"{trv_key}_battery_low"] = battery_low

        # Check main temperature sensor
        if self.coordinator.room_config.main_temp_sensor_id:
            state = self.hass.states.get(self.coordinator.room_config.main_temp_sensor_id)
            if state:
                battery = state.attributes.get("battery")
                battery_low = state.attributes.get("battery_low")

                sensor_key = self.coordinator.room_config.main_temp_sensor_id.replace("sensor.", "").replace(".", "_")
                if battery is not None:
                    try:
                        attributes[f"{sensor_key}_battery"] = float(battery)
                    except (ValueError, TypeError):
                        attributes[f"{sensor_key}_battery"] = battery
                if battery_low is not None:
                    attributes[f"{sensor_key}_battery_low"] = battery_low

        # Check humidity sensor
        if self.coordinator.room_config.humidity_sensor_id:
            state = self.hass.states.get(self.coordinator.room_config.humidity_sensor_id)
            if state:
                battery = state.attributes.get("battery")
                battery_low = state.attributes.get("battery_low")

                sensor_key = self.coordinator.room_config.humidity_sensor_id.replace("sensor.", "").replace(".", "_")
                if battery is not None:
                    try:
                        attributes[f"{sensor_key}_battery"] = float(battery)
                    except (ValueError, TypeError):
                        attributes[f"{sensor_key}_battery"] = battery
                if battery_low is not None:
                    attributes[f"{sensor_key}_battery_low"] = battery_low

        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYOverrideDetailSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for manual override details."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:thermometer-alert"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_override_details"
        self._attr_name = "Override Details"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        override_count = len(self.coordinator.override_manager._overrides)
        if override_count == 0:
            return "No active overrides"
        return f"{override_count} active override(s)"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {
            "override_count": len(self.coordinator.override_manager._overrides),
            "timeout_mode": self.coordinator.get_override_timeout(),
        }

        # Add per-TRV override details
        for entity_id, override in self.coordinator.override_manager._overrides.items():
            trv_key = entity_id.replace("climate.", "").replace(".", "_")
            attributes[f"{trv_key}_scheduled_temp"] = round(override.scheduled_temp, 1)
            attributes[f"{trv_key}_override_temp"] = round(override.override_temp, 1)
            attributes[f"{trv_key}_started_at"] = override.started_at.isoformat()
            attributes[f"{trv_key}_expires_at"] = (
                override.expires_at.isoformat() if override.expires_at else "never"
            )
            attributes[f"{trv_key}_timeout_mode"] = override.timeout_mode

        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
