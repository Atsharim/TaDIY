"""Coordinator for TaDIY - Adaptive Climate Orchestrator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    DOMAIN,
)
from .core.temperature import calculate_fused_temperature, SensorReading
from .core.window import WindowState
from .models.room import RoomConfig, RoomData

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class TaDIYDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RoomData]]):
    """Coordinator for TaDIY data management."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry,
        store: Store[dict[str, Any]]
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.store = store
        self.rooms: list[RoomConfig] = []
        self._load_rooms_from_options()
        _LOGGER.debug("TaDIY Coordinator initialized with %d rooms", len(self.rooms))

    def _load_rooms_from_options(self) -> None:
        """Load room configurations from options."""
        rooms_data = self.entry.options.get(CONF_ROOMS, [])
        self.rooms = [
            RoomConfig(
                name=room[CONF_ROOM_NAME],
                trv_entity_ids=room[CONF_TRV_ENTITIES],
                main_temp_sensor_id=room[CONF_MAIN_TEMP_SENSOR],
                window_sensor_ids=room.get(CONF_WINDOW_SENSORS, []),
                weather_entity_id=room.get(CONF_WEATHER_ENTITY, ""),
                outdoor_sensor_id=room.get(CONF_OUTDOOR_SENSOR, ""),
            )
            for room in rooms_data
        ]
        _LOGGER.info("Loaded %d room(s) from config", len(self.rooms))

    async def _async_update_data(self) -> dict[str, RoomData]:
        """Fetch data from TRVs and sensors."""
        if not self.rooms:
            _LOGGER.debug("No rooms configured, skipping update")
            return {}

        room_data: dict[str, RoomData] = {}

        for room in self.rooms:
            try:
                data = await self._update_room(room)
                room_data[room.name] = data
            except Exception as err:
                _LOGGER.warning("Error updating room %s: %s", room.name, err)
                continue

        return room_data

    async def _update_room(self, room: RoomConfig) -> RoomData:
        """Update data for a single room."""
        
        # Temperatur vom Haupt-Sensor
        main_temp = self._get_sensor_value(room.main_temp_sensor_id)
        
        # TRV-Daten sammeln
        trv_states = [self.hass.states.get(trv_id) for trv_id in room.trv_entity_ids]
        trv_temps = [
            float(state.attributes.get("current_temperature", 0))
            for state in trv_states if state
        ]
        
        # Temperatur-Fusion (Haupt-Sensor + TRVs gewichtet)
        readings = [SensorReading(room.main_temp_sensor_id, main_temp, weight=2.0)]
        for i, temp in enumerate(trv_temps):
            if temp > 0:
                readings.append(SensorReading(room.trv_entity_ids[i], temp, weight=1.0))
        
        fused_temp = calculate_fused_temperature(readings) or main_temp

        # Fenster-Status
        window_state = self._check_windows(room)

        # Außen-Temperatur
        outdoor_temp = None
        if room.outdoor_sensor_id:
            outdoor_temp = self._get_sensor_value(room.outdoor_sensor_id)

        return RoomData(
            room_name=room.name,
            current_temperature=fused_temp,
            main_sensor_temperature=main_temp,
            trv_temperatures=trv_temps,
            window_state=window_state,
            outdoor_temperature=outdoor_temp,
            last_update=dt_util.utcnow(),
        )

    def _get_sensor_value(self, entity_id: str) -> float:
        """Get numeric sensor value."""
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _check_windows(self, room: RoomConfig) -> WindowState:
        """Check window sensors (OR logic)."""
        if not room.window_sensor_ids:
            return WindowState(is_open=False, reason="no_sensors")

        for sensor_id in room.window_sensor_ids:
            state = self.hass.states.get(sensor_id)
            if state and state.state == "on":
                return WindowState(
                    is_open=True,
                    last_change=dt_util.parse_datetime(state.last_changed),
                    reason=f"sensor_{sensor_id}_open"
                )

        return WindowState(is_open=False, reason="all_closed")

    async def async_reload_rooms(self) -> None:
        """Reload room configs and refresh data."""
        self._load_rooms_from_options()
        await self.async_refresh()
        _LOGGER.info("Rooms reloaded and data refreshed")
