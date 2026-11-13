"""Sensor platform for TaDIY integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ICON_COMFORT,
    ICON_ENERGY,
    ICON_LEARNING,
    ICON_TEMPERATURE,
    ICON_WINDOW,
    WINDOW_STATE_CLOSED,
    WINDOW_STATE_CLOSED_COOLDOWN,
    WINDOW_STATE_OPEN_GRACE,
    WINDOW_STATE_OPEN_HEATING_STOPPED,
)
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


def _get_window_sensor_state(data: Any) -> str:
    """Resolve room window state to translation state key."""
    if not data or not getattr(data, "window_state", None):
        return WINDOW_STATE_CLOSED
    ws = data.window_state
    if ws.heating_should_stop:
        if ws.is_open and ws.timeout_ends_at is not None:
            return WINDOW_STATE_CLOSED_COOLDOWN
        return WINDOW_STATE_OPEN_HEATING_STOPPED
    if ws.timeout_active:
        return WINDOW_STATE_OPEN_GRACE
    return WINDOW_STATE_CLOSED


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
        available_fn=lambda data: (
            data is not None and data.current_temperature is not None
        ),
    ),
    TaDIYSensorEntityDescription(
        key="target_temperature",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: data.target_temperature if data else None,
        available_fn=lambda data: (
            data is not None and data.target_temperature is not None
        ),
    ),
    TaDIYSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.humidity, 1) if data and data.humidity is not None else None
        ),
        available_fn=lambda data: data is not None and data.humidity is not None,
    ),
    TaDIYSensorEntityDescription(
        key="window_state",
        translation_key="window_state",
        name="Window State",
        icon=ICON_WINDOW,
        value_fn=_get_window_sensor_state,
        available_fn=lambda data: data is not None,
        attr_fn=lambda data: (
            data.window_state.to_dict()
            if data and getattr(data, "window_state", None)
            else {}
        ),
    ),
    TaDIYSensorEntityDescription(
        key="heating_rate",
        name="Heating Rate",
        native_unit_of_measurement="°C/h",
        icon=ICON_LEARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.heating_rate, 2)
            if data and data.heating_rate is not None
            else None
        ),
        available_fn=lambda data: data is not None,
        attr_fn=lambda data: (
            {
                "sample_count": (
                    data.heating_rate_sample_count
                    if hasattr(data, "heating_rate_sample_count")
                    else 0
                ),
                "confidence": (
                    round(data.heating_rate_confidence, 2)
                    if hasattr(data, "heating_rate_confidence")
                    else 0.0
                ),
                "confidence_percent": (
                    f"{round(data.heating_rate_confidence * 100)}%"
                    if hasattr(data, "heating_rate_confidence")
                    else "0%"
                ),
                "last_updated": (
                    data.heating_rate_last_updated.isoformat()
                    if hasattr(data, "heating_rate_last_updated")
                    and data.heating_rate_last_updated
                    else None
                ),
            }
            if data
            else {}
        ),
    ),
    TaDIYSensorEntityDescription(
        key="main_sensor_temperature",
        name="Main Sensor Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: (
            round(data.main_sensor_temperature, 2)
            if data and data.main_sensor_temperature
            else None
        ),
        available_fn=lambda data: (
            data is not None and data.main_sensor_temperature is not None
        ),
    ),
    TaDIYSensorEntityDescription(
        key="trv_temperatures",
        name="TRV Temperatures",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon=ICON_TEMPERATURE,
        value_fn=lambda data: (
            round(sum(data.trv_temperatures) / len(data.trv_temperatures), 2)
            if data and data.trv_temperatures
            else None
        ),
        available_fn=lambda data: data is not None and data.trv_temperatures,
        attr_fn=lambda data: (
            {
                "trv_count": len(data.trv_temperatures)
                if data and data.trv_temperatures
                else 0,
                "trv_values": [round(t, 2) for t in data.trv_temperatures]
                if data and data.trv_temperatures
                else [],
                "min_trv_temp": round(min(data.trv_temperatures), 2)
                if data and data.trv_temperatures
                else None,
                "max_trv_temp": round(max(data.trv_temperatures), 2)
                if data and data.trv_temperatures
                else None,
            }
            if data
            else {}
        ),
    ),
    TaDIYSensorEntityDescription(
        key="override_status",
        name="Override Status",
        icon="mdi:thermometer-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: "Active" if data and data.override_active else "None",
        available_fn=lambda data: data is not None,
        attr_fn=lambda data: (
            {
                "override_count": data.override_count
                if hasattr(data, "override_count")
                else 0,
            }
            if data
            else {}
        ),
    ),
)

HUB_SENSOR_TYPES: tuple[TaDIYSensorEntityDescription, ...] = (
    # Note: hub_mode is provided by select.py (TaDIYHubSelect), not as a sensor
    # to avoid redundancy - the Select entity both shows and allows changing the mode
    TaDIYSensorEntityDescription(
        key="location_status",
        name="Location Status",
        icon="mdi:home-account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.get("location_status", "unknown") if data else "unknown"
        ),
        attr_fn=lambda data: data.get("location_attributes", {}) if data else {},
    ),
    TaDIYSensorEntityDescription(
        key="weather_prediction",
        name="Weather Prediction",
        icon="mdi:weather-partly-cloudy",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.get("weather_prediction", {}).get("trend", "unknown")
            if data
            else "unknown"
        ),
        available_fn=lambda data: (
            data is not None
            and data.get("weather_prediction", {}).get("available", False)
        ),
        attr_fn=lambda data: data.get("weather_prediction", {}) if data else {},
    ),
    TaDIYSensorEntityDescription(
        key="boiler_temperature",
        name="Vorlauftemperatur",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("boiler_temperature") if data else None,
        available_fn=lambda data: (
            data is not None and data.get("boiler_temperature") is not None
        ),
        attr_fn=lambda data: {
            "source_sensor": data.get("boiler_temp_sensor_id"),
            "sensor_available": data.get("boiler_sensor_available", True),
            "boiler_active": data.get("boiler_active", False),
        } if data else {},
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

        # Add room comfort sensor
        entities.append(TaDIYRoomComfortSensor(coordinator, entry))

        # Add heating time sensor
        entities.append(TaDIYHeatingTimeSensor(coordinator, entry))

        # Add energy savings sensor
        entities.append(TaDIYEnergySavingsSensor(coordinator, entry))

        _LOGGER.info("Added %d room sensor entities", len(entities))

    async_add_entities(entities)


class TaDIYRoomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Room Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry
    ) -> None:
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
            try:
                attrs = self.entity_description.attr_fn(self.coordinator.data)
                return attrs if attrs else {}
            except Exception as err:
                _LOGGER.error(
                    "Error getting attributes for %s: %s",
                    self.entity_description.key,
                    err,
                    exc_info=True,
                )
                return {}
        return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYHubSensor(CoordinatorEntity, SensorEntity):
    """Representation of a TaDIY Hub Sensor."""

    entity_description: TaDIYSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, coordinator, description: TaDIYSensorEntityDescription, entry: ConfigEntry
    ) -> None:
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

        # Count TRVs from room config (not from _calibrations which may be empty)
        total_trvs = len(self.coordinator.room_config.trv_entity_ids)

        # Count active calibrations (only if TRV exists in _calibrations)
        active_calibrations = 0
        for trv_id in self.coordinator.room_config.trv_entity_ids:
            if trv_id in cal_mgr._calibrations:
                if cal_mgr._calibrations[trv_id].mode != "disabled":
                    active_calibrations += 1
            else:
                # If not in _calibrations yet, it's auto by default (active)
                active_calibrations += 1

        return f"{active_calibrations}/{total_trvs}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        cal_mgr = self.coordinator.calibration_manager
        room_data = self.coordinator.current_room_data

        attributes = {
            "main_sensor_temp": round(room_data.main_sensor_temperature, 2)
            if room_data
            else None,
            "fused_temp": round(room_data.current_temperature, 2)
            if room_data
            else None,
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
                attributes[f"{trv_key}_offset"] = round(cal_info["offset"], 1)
                attributes[f"{trv_key}_current_temp"] = (
                    round(trv_temp, 2) if trv_temp else None
                )
                attributes[f"{trv_key}_last_room_temp"] = (
                    round(cal_info["last_room_temp"], 2)
                    if cal_info["last_room_temp"]
                    else None
                )
                attributes[f"{trv_key}_last_trv_temp"] = (
                    round(cal_info["last_trv_temp"], 2)
                    if cal_info["last_trv_temp"]
                    else None
                )
                attributes[f"{trv_key}_last_calibrated"] = cal_info["last_calibrated"]
            else:
                # No calibration data yet - use defaults
                attributes[f"{trv_key}_mode"] = "auto"
                attributes[f"{trv_key}_offset"] = 0.0
                attributes[f"{trv_key}_current_temp"] = (
                    round(trv_temp, 2) if trv_temp else None
                )
                attributes[f"{trv_key}_last_room_temp"] = None
                attributes[f"{trv_key}_last_trv_temp"] = None
                attributes[f"{trv_key}_last_calibrated"] = None

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

    def _get_device_battery_info(
        self, entity_id: str
    ) -> tuple[float | None, bool | None, bool]:
        """Resolve battery percentage, low-flag, and offline state for an entity or its device."""
        state = self.hass.states.get(entity_id)
        if not state:
            return None, None, True

        is_offline = state.state in ("unavailable", "unknown")
        battery_level = None
        battery_low = None

        # 1. Direct attributes on entity
        for attr in ("battery", "battery_level"):
            val = state.attributes.get(attr)
            if val is not None:
                try:
                    battery_level = float(val)
                    break
                except (ValueError, TypeError):
                    pass

        raw_low = state.attributes.get("battery_low")
        if raw_low is not None:
            battery_low = bool(raw_low)

        # 2. Associated device entities in device registry / entity registry
        if battery_level is None:
            try:
                from homeassistant.helpers import entity_registry as er

                ent_reg = er.async_get(self.hass)
                entry = ent_reg.async_get(entity_id)
                if entry and entry.device_id:
                    for sibling in er.async_entries_for_device(ent_reg, entry.device_id):
                        if sibling.entity_id == entity_id:
                            continue
                        sib_state = self.hass.states.get(sibling.entity_id)
                        if not sib_state or sib_state.state in ("unavailable", "unknown"):
                            continue

                        # Check battery sensor
                        if sibling.domain == "sensor" and (
                            sibling.device_class == "battery"
                            or sibling.original_device_class == "battery"
                            or sibling.entity_id.endswith("_battery")
                            or sibling.entity_id.endswith("_battery_level")
                            or sibling.entity_id.endswith("_battery_plus")
                        ):
                            try:
                                battery_level = float(sib_state.state)
                                break
                            except (ValueError, TypeError):
                                pass

                        # Check binary_sensor for low battery
                        if sibling.domain == "binary_sensor" and (
                            sibling.device_class == "battery"
                            or sibling.original_device_class == "battery"
                            or sibling.entity_id.endswith("_battery_low")
                        ):
                            if sib_state.state == "on":
                                battery_low = True
            except Exception:
                pass

        # 3. Heuristic name fallback if device registry is unavailable
        if battery_level is None:
            stem = entity_id.split(".", 1)[-1]
            # Strip prefixes / suffixes
            clean_stem = (
                stem.replace("_window", "")
                .replace("_contact", "")
                .replace("_temperature", "")
            )
            for candidate in (
                f"sensor.{stem}_battery",
                f"sensor.{stem}_battery_level",
                f"sensor.{stem}_battery_plus",
                f"sensor.{clean_stem}_battery",
                f"sensor.{clean_stem}_battery_plus",
            ):
                cand_state = self.hass.states.get(candidate)
                if cand_state and cand_state.state not in ("unavailable", "unknown"):
                    try:
                        battery_level = float(cand_state.state)
                        break
                    except (ValueError, TypeError):
                        pass

        if battery_level is not None and battery_low is None:
            battery_low = battery_level < 20.0
        elif battery_low is True and battery_level is None:
            battery_level = 10.0

        return battery_level, battery_low, is_offline

    def _collect_monitored_entities(self) -> list[str]:
        """Collect all device entities associated with this room."""
        entities = list(self.coordinator.room_config.trv_entity_ids)
        if self.coordinator.room_config.main_temp_sensor_id:
            entities.append(self.coordinator.room_config.main_temp_sensor_id)
        if self.coordinator.room_config.humidity_sensor_id:
            entities.append(self.coordinator.room_config.humidity_sensor_id)
        if getattr(self.coordinator.room_config, "window_sensor_ids", None):
            entities.extend(self.coordinator.room_config.window_sensor_ids)
        return entities

    @property
    def native_value(self) -> str:
        """Return the state of the sensor (count of low batteries and offline sensors)."""
        low_battery_count = 0
        total_battery_count = 0
        offline_count = 0

        for entity_id in self._collect_monitored_entities():
            bat_lvl, is_low, is_offline = self._get_device_battery_info(entity_id)
            if is_offline:
                offline_count += 1
            if bat_lvl is not None:
                total_battery_count += 1
                if is_low:
                    low_battery_count += 1

        if offline_count > 0 and low_battery_count > 0:
            return f"{low_battery_count} Low, {offline_count} Offline"
        if offline_count > 0:
            return f"{offline_count} Sensor{'s' if offline_count > 1 else ''} Offline"
        if total_battery_count == 0:
            return "No battery devices"
        if low_battery_count == 0:
            return "All OK"
        return f"{low_battery_count}/{total_battery_count} Low"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: dict[str, Any] = {
            "offline_devices": [],
            "low_battery_devices": [],
            "device_details": [],
        }

        for entity_id in self._collect_monitored_entities():
            bat_lvl, is_low, is_offline = self._get_device_battery_info(entity_id)
            state = self.hass.states.get(entity_id)
            friendly_name = (
                state.attributes.get("friendly_name", entity_id) if state else entity_id
            )
            key = entity_id.replace("climate.", "").replace("sensor.", "").replace("binary_sensor.", "").replace(".", "_")

            if is_offline:
                attributes["offline_devices"].append(entity_id)
            if bat_lvl is not None:
                attributes[f"{key}_battery"] = bat_lvl
            if is_low is not None:
                attributes[f"{key}_battery_low"] = is_low
                if is_low:
                    attributes["low_battery_devices"].append(entity_id)

            dev_class = state.attributes.get("device_class") if state else None
            clean_lower = entity_id.lower()
            name_lower = friendly_name.lower()

            if entity_id.startswith("climate."):
                dev_type = "trv"
            elif dev_class == "door" or any(k in clean_lower or k in name_lower for k in ("tuer", "tür", "door", "tor", "gate")):
                dev_type = "door"
            elif dev_class == "window" or any(k in clean_lower or k in name_lower for k in ("window", "fenster", "roof")):
                dev_type = "window"
            elif dev_class == "humidity" or any(k in clean_lower or k in name_lower for k in ("humidity", "feucht")):
                dev_type = "humidity"
            elif dev_class == "temperature" or any(k in clean_lower or k in name_lower for k in ("temp", "temperatur")):
                dev_type = "temp"
            else:
                dev_type = "sensor"

            attributes["device_details"].append(
                {
                    "entity_id": entity_id,
                    "name": friendly_name,
                    "type": dev_type,
                    "battery": bat_lvl,
                    "is_low": is_low,
                    "is_offline": is_offline,
                }
            )

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
        """Return the state of the sensor showing current mode and target."""
        hub_mode = self.coordinator.get_hub_mode()
        scheduled_target = self.coordinator.get_scheduled_target()
        override_count = len(self.coordinator.override_manager._overrides)

        # If overrides exist, show override temperature(s)
        if override_count > 0:
            # Get first override (representative if multiple TRVs)
            first_override = next(
                iter(self.coordinator.override_manager._overrides.values())
            )
            override_temp = first_override.override_temp
            scheduled_temp = first_override.scheduled_temp
            return f"{hub_mode}: {override_count} override(s), {override_temp:.1f}°C (scheduled: {scheduled_temp:.1f}°C)"

        # No overrides: show scheduled target
        target_str = f"{scheduled_target:.1f}°C" if scheduled_target else "None"
        return f"{hub_mode}: {target_str}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        # Get current hub mode and scheduled target
        hub_mode = self.coordinator.get_hub_mode()
        scheduled_target = self.coordinator.get_scheduled_target()
        room_data = self.coordinator.current_room_data

        attributes = {
            # Room status info
            "hub_mode": hub_mode,
            "scheduled_target": round(scheduled_target, 1)
            if scheduled_target
            else None,
            "current_target": round(room_data.target_temperature, 1)
            if room_data
            else None,
            "current_temperature": round(room_data.current_temperature, 1)
            if room_data
            else None,
            "heating_active": room_data.heating_active if room_data else False,
            "enforce_schedule": hub_mode not in ("manual", "off"),
            # Override info
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


from .core.temperature import (
    COMFORT_HUMIDITY_ACCEPTABLE_MAX,
    COMFORT_HUMIDITY_ACCEPTABLE_MIN,
    COMFORT_HUMIDITY_DRY,
    COMFORT_HUMIDITY_IDEAL,
    COMFORT_HUMIDITY_MAX,
    COMFORT_HUMIDITY_MIN,
    COMFORT_HUMIDITY_WET,
    COMFORT_TEMP_ACCEPTABLE_MAX,
    COMFORT_TEMP_ACCEPTABLE_MIN,
    COMFORT_TEMP_COLD,
    COMFORT_TEMP_IDEAL,
    COMFORT_TEMP_MAX,
    COMFORT_TEMP_MIN,
    COMFORT_TEMP_WARM,
    calculate_comfort as _calculate_comfort,
)


class TaDIYRoomComfortSensor(CoordinatorEntity, SensorEntity):
    """Sensor that combines temperature and humidity into a comfort score."""

    _attr_has_entity_name = True
    _attr_icon = ICON_COMFORT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_room_comfort"
        self._attr_name = "Room Comfort"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    @property
    def native_value(self) -> int | None:
        """Return comfort score 0-100."""
        data = self.coordinator.data
        if data is None:
            return None
        return _calculate_comfort(
            data.current_temperature,
            data.humidity,
        )["comfort_score"]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit."""
        return "%"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return comfort details as attributes."""
        data = self.coordinator.data
        if data is None:
            _LOGGER.debug("Room Comfort: No data available for attributes")
            return {}
        try:
            attrs = _calculate_comfort(
                data.current_temperature,
                data.humidity,
            )
            return attrs
        except Exception as err:
            _LOGGER.error(
                "Error calculating comfort attributes: %s",
                err,
                exc_info=True,
            )
            return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TaDIYHeatingTimeSensor(CoordinatorEntity, SensorEntity):
    """Tracks cumulative heating time with persistent daily/weekly/monthly stats."""

    _attr_has_entity_name = True
    _attr_icon = ICON_ENERGY
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_heating_time_today"
        self._attr_name = "Heating Time Today"
        self._attr_device_info = get_device_info(entry, coordinator.hass)
        self._last_heating_check: float | None = None
        self._last_date: str | None = None
        self._save_counter: int = 0

        # Restore from persistent storage
        stats = getattr(coordinator, "heating_stats", {}) or {}
        self._today_seconds: float = stats.get("today_seconds", 0.0)
        self._last_date = stats.get("last_date", None)
        # Daily history: {date_str: seconds} - keep last 31 days
        self._daily_history: dict[str, float] = stats.get("daily_history", {})

    @property
    def native_value(self) -> float:
        """Return heating hours today."""
        return round(self._today_seconds / 3600.0, 2)

    def _week_hours(self) -> float:
        """Sum heating hours for the current ISO week."""
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        monday = now - timedelta(days=now.weekday())
        total = self._today_seconds
        for i in range(1, 7):
            day = (monday + timedelta(days=i - 1)).strftime("%Y-%m-%d")
            if day != self._last_date:
                total += self._daily_history.get(day, 0.0)
        return round(total / 3600.0, 2)

    def _month_hours(self) -> float:
        """Sum heating hours for the current calendar month."""
        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        prefix = now.strftime("%Y-%m-")
        total = self._today_seconds
        for day, secs in self._daily_history.items():
            if day.startswith(prefix) and day != self._last_date:
                total += secs
        return round(total / 3600.0, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return heating time details with weekly/monthly stats."""
        data = self.coordinator.data
        return {
            "heating_active": data.heating_active if data else False,
            "seconds_today": round(self._today_seconds),
            "hours_today": self.native_value,
            "hours_this_week": self._week_hours(),
            "hours_this_month": self._month_hours(),
        }

    def _persist(self) -> None:
        """Save stats to coordinator storage (debounced)."""
        self._save_counter += 1
        # Save every 10 updates (~10 minutes at 60s interval)
        if self._save_counter >= 10:
            self._save_counter = 0
            self.coordinator.heating_stats = {
                "today_seconds": self._today_seconds,
                "last_date": self._last_date,
                "daily_history": self._daily_history,
            }
            self.coordinator.hass.async_create_task(
                self.coordinator.async_save_heating_stats()
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Accumulate heating time and update HA state."""
        from homeassistant.util import dt as dt_util

        # Initialize from persisted stats if this is first update
        if self._last_date is None:
            stats = self.coordinator.heating_stats
            self._today_seconds = stats.get("today_seconds", 0.0)
            self._last_date = stats.get("last_date", None)
            self._daily_history = stats.get("daily_history", {})

        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")

        # Day rollover: archive yesterday, reset counter
        if self._last_date is not None and self._last_date != today_str:
            self._daily_history[self._last_date] = self._today_seconds
            # Prune history older than 31 days
            from datetime import timedelta as _td

            cutoff = (now - _td(days=31)).strftime("%Y-%m-%d")
            self._daily_history = {
                d: s for d, s in self._daily_history.items() if d >= cutoff
            }
            self._today_seconds = 0.0
            self._last_heating_check = None
            # Force-save on day rollover
            self._save_counter = 9

        self._last_date = today_str

        # Accumulate heating time
        data = self.coordinator.data
        if data is not None and data.heating_active:
            now_ts = now.timestamp()
            if self._last_heating_check is not None:
                elapsed = now_ts - self._last_heating_check
                # Only accumulate reasonable intervals (max 5 minutes)
                if 0 < elapsed <= 300:
                    self._today_seconds += elapsed
            self._last_heating_check = now_ts
        else:
            self._last_heating_check = None

        self._persist()
        self.async_write_ha_state()


class TaDIYEnergySavingsSensor(CoordinatorEntity, SensorEntity):
    """Tracks energy savings from various smart heating decisions."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:leaf"
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_energy_savings"
        self._attr_name = "Energy Savings Today"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

        # Tracking state
        self._last_check: float | None = None
        self._last_date: str | None = None
        self._save_counter: int = 0

        # Restore from persistent storage
        stats = getattr(coordinator, "savings_stats", {}) or {}
        self._window_seconds: float = stats.get("window_seconds", 0.0)
        self._away_seconds: float = stats.get("away_seconds", 0.0)
        self._weather_seconds: float = stats.get("weather_seconds", 0.0)
        self._last_date = stats.get("last_date", None)
        # Daily history
        self._daily_history: dict[str, dict] = stats.get("daily_history", {})

        # Default power consumption (can be configured via options)
        # Average heating power in kW when heating is active
        self._heating_power_kw: float = (
            coordinator.room_config.heating_power_kw
            if hasattr(coordinator.room_config, "heating_power_kw")
            else 2.0
        )
        # Energy price in €/kWh
        self._energy_price: float = (
            coordinator.room_config.energy_price
            if hasattr(coordinator.room_config, "energy_price")
            else 0.30
        )

    @property
    def native_value(self) -> float:
        """Return total energy savings today in kWh."""
        total_seconds = (
            self._window_seconds + self._away_seconds + self._weather_seconds
        )
        total_hours = total_seconds / 3600.0
        savings_kwh = total_hours * self._heating_power_kw
        return round(savings_kwh, 2)

    def _calculate_monetary_savings(self) -> float:
        """Calculate monetary savings in €."""
        kwh = self.native_value
        return round(kwh * self._energy_price, 2)

    def _week_savings(self) -> dict[str, float]:
        """Sum savings for the current ISO week."""
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        monday = now - timedelta(days=now.weekday())

        total_window = self._window_seconds
        total_away = self._away_seconds
        total_weather = self._weather_seconds

        for i in range(1, 7):
            day = (monday + timedelta(days=i - 1)).strftime("%Y-%m-%d")
            if day != self._last_date and day in self._daily_history:
                hist = self._daily_history[day]
                total_window += hist.get("window_seconds", 0.0)
                total_away += hist.get("away_seconds", 0.0)
                total_weather += hist.get("weather_seconds", 0.0)

        total_hours = (total_window + total_away + total_weather) / 3600.0
        kwh = total_hours * self._heating_power_kw
        return {
            "kwh": round(kwh, 2),
            "euros": round(kwh * self._energy_price, 2),
            "hours": round(total_hours, 1),
        }

    def _month_savings(self) -> dict[str, float]:
        """Sum savings for the current calendar month."""
        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        prefix = now.strftime("%Y-%m-")

        total_window = self._window_seconds
        total_away = self._away_seconds
        total_weather = self._weather_seconds

        for day, hist in self._daily_history.items():
            if day.startswith(prefix) and day != self._last_date:
                total_window += hist.get("window_seconds", 0.0)
                total_away += hist.get("away_seconds", 0.0)
                total_weather += hist.get("weather_seconds", 0.0)

        total_hours = (total_window + total_away + total_weather) / 3600.0
        kwh = total_hours * self._heating_power_kw
        return {
            "kwh": round(kwh, 2),
            "euros": round(kwh * self._energy_price, 2),
            "hours": round(total_hours, 1),
        }

    def _last_30_days_savings(self) -> dict[str, float]:
        """Sum savings for the last 30 days (rolling window)."""
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        cutoff_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        total_window = self._window_seconds
        total_away = self._away_seconds
        total_weather = self._weather_seconds

        for day, hist in self._daily_history.items():
            if day >= cutoff_date and day != self._last_date:
                total_window += hist.get("window_seconds", 0.0)
                total_away += hist.get("away_seconds", 0.0)
                total_weather += hist.get("weather_seconds", 0.0)

        total_hours = (total_window + total_away + total_weather) / 3600.0
        kwh = total_hours * self._heating_power_kw
        return {
            "kwh": round(kwh, 2),
            "euros": round(kwh * self._energy_price, 2),
            "hours": round(total_hours, 1),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed savings breakdown."""
        week = self._week_savings()
        month = self._month_savings()
        last_30 = self._last_30_days_savings()

        # Calculate % savings (based on 24h potential heating time)
        total_hours_today = (
            self._window_seconds + self._away_seconds + self._weather_seconds
        ) / 3600.0
        savings_percent_today = (
            (total_hours_today / 24.0) * 100 if total_hours_today > 0 else 0.0
        )
        savings_percent_week = (
            (week["hours"] / (24.0 * 7)) * 100 if week["hours"] > 0 else 0.0
        )
        savings_percent_month = (
            (month["hours"] / (24.0 * 30)) * 100 if month["hours"] > 0 else 0.0
        )
        savings_percent_last_30 = (
            (last_30["hours"] / (24.0 * 30)) * 100 if last_30["hours"] > 0 else 0.0
        )

        return {
            # Today's breakdown
            "window_open_hours": round(self._window_seconds / 3600.0, 2),
            "away_mode_hours": round(self._away_seconds / 3600.0, 2),
            "weather_hours": round(self._weather_seconds / 3600.0, 2),
            "total_hours_today": round(total_hours_today, 2),
            "total_kwh_today": self.native_value,
            "total_euros_today": self._calculate_monetary_savings(),
            "savings_percent_today": round(savings_percent_today, 1),
            # This week
            "total_kwh_this_week": week["kwh"],
            "total_euros_this_week": week["euros"],
            "total_hours_this_week": week["hours"],
            "savings_percent_week": round(savings_percent_week, 1),
            # This month
            "total_kwh_this_month": month["kwh"],
            "total_euros_this_month": month["euros"],
            "total_hours_this_month": month["hours"],
            "savings_percent_month": round(savings_percent_month, 1),
            # Last 30 days
            "total_kwh_last_30_days": last_30["kwh"],
            "total_euros_last_30_days": last_30["euros"],
            "total_hours_last_30_days": last_30["hours"],
            "savings_percent_last_30_days": round(savings_percent_last_30, 1),
            # Configuration
            "heating_power_kw": self._heating_power_kw,
            "energy_price_eur_kwh": self._energy_price,
        }

    def _persist(self) -> None:
        """Save stats to coordinator storage (debounced)."""
        self._save_counter += 1
        # Save every 10 updates (~10 minutes at 60s interval)
        if self._save_counter >= 10:
            self._save_counter = 0
            self.coordinator.savings_stats = {
                "window_seconds": self._window_seconds,
                "away_seconds": self._away_seconds,
                "weather_seconds": self._weather_seconds,
                "last_date": self._last_date,
                "daily_history": self._daily_history,
            }
            self.coordinator.hass.async_create_task(
                self.coordinator.async_save_savings_stats()
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Track savings based on heating decisions."""
        from homeassistant.util import dt as dt_util

        # Initialize from persisted stats if this is first update
        if self._last_date is None:
            stats = self.coordinator.savings_stats
            self._window_seconds = stats.get("window_seconds", 0.0)
            self._away_seconds = stats.get("away_seconds", 0.0)
            self._weather_seconds = stats.get("weather_seconds", 0.0)
            self._last_date = stats.get("last_date", None)
            self._daily_history = stats.get("daily_history", {})

        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")

        # Day rollover: archive yesterday, reset counters
        if self._last_date is not None and self._last_date != today_str:
            self._daily_history[self._last_date] = {
                "window_seconds": self._window_seconds,
                "away_seconds": self._away_seconds,
                "weather_seconds": self._weather_seconds,
            }
            # Prune history older than 31 days
            from datetime import timedelta as _td

            cutoff = (now - _td(days=31)).strftime("%Y-%m-%d")
            self._daily_history = {
                d: s for d, s in self._daily_history.items() if d >= cutoff
            }
            self._window_seconds = 0.0
            self._away_seconds = 0.0
            self._weather_seconds = 0.0
            self._last_check = None
            # Force-save on day rollover
            self._save_counter = 9

        self._last_date = today_str

        # Track savings
        data = self.coordinator.data
        if data is not None:
            now_ts = now.timestamp()

            if self._last_check is not None:
                elapsed = now_ts - self._last_check
                # Only accumulate reasonable intervals (max 5 minutes)
                if 0 < elapsed <= 300:
                    # Check what prevented heating
                    # Window open
                    if data.window_state.heating_should_stop:
                        self._window_seconds += elapsed
                    # Away mode (location-based reduction)
                    elif (
                        self.coordinator.hub_coordinator
                        and self.coordinator.hub_coordinator.should_reduce_heating_for_away()
                        and not data.heating_active
                    ):
                        self._away_seconds += elapsed
                    # Weather-based (outdoor temp warm enough)
                    elif (
                        data.outdoor_temperature is not None
                        and data.outdoor_temperature > 15.0  # Configurable threshold
                        and not data.heating_active
                        and data.target_temperature is not None
                        and data.current_temperature < data.target_temperature
                    ):
                        self._weather_seconds += elapsed

            self._last_check = now_ts

        self._persist()
        self.async_write_ha_state()
