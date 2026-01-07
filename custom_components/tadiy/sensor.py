"""Sensor platform for TaDIY."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LAST_LEARNING_UPDATE,
    ATTR_LEARNING_SAMPLES,
    DOMAIN,
    HEALTH_STATUS_CRITICAL,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_HEALTHY,
    ICON_LEARNING,
    ICON_TEMPERATURE,
    ICON_WINDOW,
    MANUFACTURER,
    MODEL_NAME,
    SENSOR_TYPE_HEALTH,
    SENSOR_TYPE_HEATING_RATE,
    SENSOR_TYPE_MAIN_TEMP,
    SENSOR_TYPE_OUTDOOR_TEMP,
    SENSOR_TYPE_WINDOW_STATE,
    WINDOW_STATE_CLOSED,
    WINDOW_STATE_CLOSED_COOLDOWN,
    WINDOW_STATE_OPEN_HEATING_STOPPED,
    WINDOW_STATE_OPEN_WITHIN_TIMEOUT,
)
from .coordinator import TaDIYDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY sensor entities."""
    coordinator: TaDIYDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    sensors = []

    for room in coordinator.rooms:
        room_name = room.name

        # Temperature sensors
        sensors.extend([
            TaDIYMainTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            ),
            TaDIYOutdoorTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            ),
            TaDIYFusedTemperatureSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            ),
        ])

        # Window state sensor
        if room.window_sensor_ids:
            sensors.append(
                TaDIYWindowStateSensor(
                    coordinator,
                    config_entry.entry_id,
                    room_name,
                )
            )

        # Heating rate sensor
        sensors.append(
            TaDIYHeatingRateSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            )
        )

        # Health sensor
        sensors.append(
            TaDIYHealthSensor(
                coordinator,
                config_entry.entry_id,
                room_name,
            )
        )

    async_add_entities(sensors)
    _LOGGER.info("TaDIY sensor platform setup complete with %d sensors", len(sensors))


class TaDIYMainTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor for main temperature."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = ICON_TEMPERATURE

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Main Temperature"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_MAIN_TEMP}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        room_data = self.coordinator.data.get(self._room_name)
        if room_data:
            return room_data.get("main_temp")
        return None


class TaDIYOutdoorTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor for outdoor temperature."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = ICON_TEMPERATURE

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Outdoor Temperature"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_OUTDOOR_TEMP}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        room_data = self.coordinator.data.get(self._room_name)
        if room_data:
            return room_data.get("outdoor_temp")
        return None


class TaDIYFusedTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor for fused temperature."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = ICON_TEMPERATURE

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Fused Temperature"
        self._attr_unique_id = f"{entry_id}_{room_name}_fused_temperature"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        room_data = self.coordinator.data.get(self._room_name)
        if room_data:
            return room_data.get("fused_temp")
        return None


class TaDIYWindowStateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for window state."""

    _attr_icon = ICON_WINDOW

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Window State"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_WINDOW_STATE}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return WINDOW_STATE_CLOSED

        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return WINDOW_STATE_CLOSED

        window_open = room_data.get("window_open", False)
        return (
            WINDOW_STATE_OPEN_HEATING_STOPPED
            if window_open
            else WINDOW_STATE_CLOSED
        )


class TaDIYHeatingRateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for heating rate with learning status."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C/h"
    _attr_icon = ICON_LEARNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Heating Rate"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_HEATING_RATE}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the heating rate."""
        if not self.coordinator.data:
            return None
        room_data = self.coordinator.data.get(self._room_name)
        if room_data:
            return room_data.get("heating_rate")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return learning status attributes."""
        attrs = {}

        if not self.coordinator.data:
            return attrs

        room_data = self.coordinator.data.get(self._room_name)
        if not room_data:
            return attrs

        heat_model = room_data.get("heat_model")
        if heat_model:
            attrs[ATTR_LEARNING_SAMPLES] = heat_model.sample_count
            attrs["confidence"] = heat_model.get_confidence()
            attrs["status"] = heat_model.get_status()
            attrs["is_default"] = heat_model.is_using_default()

            if heat_model.last_update:
                attrs[ATTR_LAST_LEARNING_UPDATE] = heat_model.last_update.isoformat()

        return attrs


class TaDIYHealthSensor(CoordinatorEntity, SensorEntity):
    """Health check sensor for room entities."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Health"
        self._attr_unique_id = f"{entry_id}_{room_name}_{SENSOR_TYPE_HEALTH}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    @property
    def native_value(self) -> str:
        """Return health status."""
        room_config = self._get_room_config()
        if not room_config:
            return HEALTH_STATUS_CRITICAL

        missing = []
        critical = False

        # Check Main Temperature Sensor
        main_temp_state = self.hass.states.get(room_config.main_temp_sensor_id)
        if not main_temp_state or main_temp_state.state in ("unknown", "unavailable"):
            missing.append(room_config.main_temp_sensor_id)
            critical = True

        # Check TRV Entities
        available_trvs = 0
        for trv_id in room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_id)
            if trv_state and trv_state.state not in ("unknown", "unavailable"):
                available_trvs += 1
            else:
                missing.append(trv_id)

        # At least 1 TRV must be available
        if available_trvs == 0:
            critical = True

        # Check Window Sensors (optional)
        if room_config.window_sensor_ids:
            for sensor_id in room_config.window_sensor_ids:
                sensor_state = self.hass.states.get(sensor_id)
                if not sensor_state or sensor_state.state in ("unknown", "unavailable"):
                    missing.append(sensor_id)

        # Check Outdoor Sensor (optional)
        if room_config.outdoor_sensor_id:
            outdoor_state = self.hass.states.get(room_config.outdoor_sensor_id)
            if not outdoor_state or outdoor_state.state in ("unknown", "unavailable"):
                missing.append(room_config.outdoor_sensor_id)

        # Determine status
        if critical:
            return HEALTH_STATUS_CRITICAL
        elif missing:
            return HEALTH_STATUS_DEGRADED
        else:
            return HEALTH_STATUS_HEALTHY

    @property
    def icon(self) -> str:
        """Return dynamic icon based on health status."""
        status = self.native_value
        if status == HEALTH_STATUS_HEALTHY:
            return "mdi:check-circle"
        elif status == HEALTH_STATUS_DEGRADED:
            return "mdi:alert-circle"
        else:
            return "mdi:close-circle"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return detailed health information."""
        room_config = self._get_room_config()
        if not room_config:
            return {}

        missing = []

        # Check Main Temp
        main_temp_state = self.hass.states.get(room_config.main_temp_sensor_id)
        main_available = main_temp_state and main_temp_state.state not in ("unknown", "unavailable")
        if not main_available:
            missing.append(room_config.main_temp_sensor_id)

        # Check TRVs
        available_trvs = 0
        for trv_id in room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_id)
            if trv_state and trv_state.state not in ("unknown", "unavailable"):
                available_trvs += 1
            else:
                missing.append(trv_id)

        # Check Window Sensors
        window_available = True
        if room_config.window_sensor_ids:
            for sensor_id in room_config.window_sensor_ids:
                sensor_state = self.hass.states.get(sensor_id)
                if not sensor_state or sensor_state.state in ("unknown", "unavailable"):
                    missing.append(sensor_id)
                    window_available = False

        # Check Outdoor Sensor
        outdoor_available = True
        if room_config.outdoor_sensor_id:
            outdoor_state = self.hass.states.get(room_config.outdoor_sensor_id)
            if not outdoor_state or outdoor_state.state in ("unknown", "unavailable"):
                missing.append(room_config.outdoor_sensor_id)
                outdoor_available = False

        return {
            "missing_entities": missing,
            "main_temp_available": main_available,
            "trv_count_configured": len(room_config.trv_entity_ids),
            "trv_count_available": available_trvs,
            "window_sensors_available": window_available if room_config.window_sensor_ids else None,
            "outdoor_sensor_available": outdoor_available if room_config.outdoor_sensor_id else None,
        }

    def _get_room_config(self):
        """Get room configuration from coordinator."""
        for room in self.coordinator.rooms:
            if room.name == self._room_name:
                return room
        return None
