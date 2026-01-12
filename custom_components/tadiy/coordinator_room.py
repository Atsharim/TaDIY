"""Room DataUpdateCoordinator for TaDIY."""
from __future__ import annotations
from datetime import timedelta
import logging
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_WINDOW_SENSORS,
    DEFAULT_HEATING_RATE,
    DOMAIN,
    STORAGE_KEY_SCHEDULES,
    STORAGE_VERSION_SCHEDULES,
    UPDATE_INTERVAL,
)
from .core.early_start import HeatUpModel
from .core.schedule import ScheduleEngine
from .core.temperature import SensorReading, calculate_fused_temperature
from .core.window import WindowState
from .models.room import RoomConfig, RoomData
_LOGGER = logging.getLogger(__name__)
MAIN_SENSOR_WEIGHT: float = 10.0
TRV_SENSOR_WEIGHT: float = 0.1
class TaDIYRoomCoordinator(DataUpdateCoordinator):
    """Room Coordinator for individual room management."""
    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        room_data: dict[str, Any],
        hub_coordinator: Any = None,
    ) -> None:
        """Initialize Room Coordinator."""
        self.entry_id = entry_id
        self.hass = hass
        self.hub_coordinator = hub_coordinator
        
        # Transform config flow data to RoomConfig format
        room_config_data = self._transform_config_data(room_data)
        self.room_config = RoomConfig.from_dict(room_config_data)
        
        self.current_room_data: RoomData | None = None
        self._heat_model = HeatUpModel(room_name=self.room_config.name)
        self.schedule_engine = ScheduleEngine()
        self.schedule_store = Store(
            hass,
            STORAGE_VERSION_SCHEDULES,
            STORAGE_KEY_SCHEDULES + "_" + entry_id,
        )
        self._boosts: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN + "_room_" + self.room_config.name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
    
    def _transform_config_data(self, room_data: dict[str, Any]) -> dict[str, Any]:
        """Transform config flow data to RoomConfig expected format."""
        return {
            "name": room_data.get(CONF_ROOM_NAME, "Unknown"),
            "trv_entity_ids": room_data.get(CONF_TRV_ENTITIES, []),
            "main_temp_sensor_id": room_data.get(CONF_MAIN_TEMP_SENSOR, ""),
            "window_sensor_ids": room_data.get(CONF_WINDOW_SENSORS, []),
            "outdoor_sensor_id": room_data.get(CONF_OUTDOOR_SENSOR, ""),
            "weather_entity_id": room_data.get("weather_entity_id", ""),
            "window_open_timeout": room_data.get("window_open_timeout", 300),
            "window_close_timeout": room_data.get("window_close_timeout", 180),
            "dont_heat_below_outdoor": room_data.get("dont_heat_below_outdoor", 20.0),
            "use_early_start": room_data.get("use_early_start", True),
            "learn_heating_rate": room_data.get("learn_heating_rate", True),
            "use_humidity_compensation": room_data.get("use_humidity_compensation", False),
        }
    
    async def async_load_schedules(self) -> None:
        """Load room schedules from storage."""
        data = await self.schedule_store.async_load()
        if not data:
            _LOGGER.info("No schedule data found for room: %s", self.room_config.name)
            return
        try:
            from .models.schedule import RoomSchedule
            room_schedule = RoomSchedule.from_dict(data)
            self.schedule_engine.update_room_schedule(self.room_config.name, room_schedule)
            _LOGGER.debug("Loaded schedule for room: %s", self.room_config.name)
        except (ValueError, KeyError) as err:
            _LOGGER.warning("Failed to load schedule for %s: %s", self.room_config.name, err)
    async def async_save_schedules(self) -> None:
        """Save room schedules to storage."""
        try:
            from .models.schedule import RoomSchedule
            if self.room_config.name in self.schedule_engine._room_schedules:
                room_schedule = self.schedule_engine._room_schedules[self.room_config.name]
                await self.schedule_store.async_save(room_schedule.to_dict())
                _LOGGER.debug("Saved schedule for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error("Failed to save schedule for %s: %s", self.room_config.name, err)
    def get_hub_settings(self) -> dict[str, Any]:
        """Get hub global settings."""
        if self.hub_coordinator:
            return self.hub_coordinator.global_settings
        return {}
    def get_hub_mode(self) -> str:
        """Get current hub mode."""
        if self.hub_coordinator:
            return self.hub_coordinator.hub_mode
        return "normal"
    def get_scheduled_target(self) -> float | None:
        """Get scheduled target temperature for this room."""
        mode = self.get_hub_mode()
        return self.schedule_engine.get_target_temperature(self.room_config.name, mode)
    def check_window_override(self, current_target: float) -> bool:
        """Check if window open overrides heating."""
        hub_settings = self.get_hub_settings()
        window_timeout = hub_settings.get("global_window_open_timeout", 30)
        if self.current_room_data and self.current_room_data.window_state.heating_should_stop:
            return True
        return False
    async def _async_update_data(self) -> RoomData | None:
        """Fetch and process room data."""
        try:
            main_temp = self._get_sensor_value(self.room_config.main_temp_sensor_id)
            outdoor_temp = self._get_sensor_value(self.room_config.outdoor_sensor_id)
            window_open = self._check_window_state(self.room_config.window_sensor_ids)
            trv_readings = []
            trv_temps = []
            for trv_id in self.room_config.trv_entity_ids:
                trv_state = self.hass.states.get(trv_id)
                if trv_state:
                    trv_current = trv_state.attributes.get("current_temperature")
                    trv_target = trv_state.attributes.get("temperature")
                    if trv_current:
                        try:
                            trv_temp = float(trv_current)
                            trv_temps.append(trv_temp)
                            trv_readings.append(
                                SensorReading(
                                    entity_id=trv_id,
                                    temperature=trv_temp,
                                    weight=TRV_SENSOR_WEIGHT,
                                )
                            )
                        except (ValueError, TypeError):
                            pass
            if main_temp is not None:
                fused_temp = main_temp
            elif trv_readings:
                fused_temp = calculate_fused_temperature(trv_readings)
            else:
                _LOGGER.warning("No valid temperature for room %s", self.room_config.name)
                fused_temp = None
            current_target = None
            for trv_id in self.room_config.trv_entity_ids:
                trv_state = self.hass.states.get(trv_id)
                if trv_state and "temperature" in trv_state.attributes:
                    current_target = float(trv_state.attributes["temperature"])
                    break
            scheduled_target = self.get_scheduled_target()
            hvac_mode = "heat"
            for trv_id in self.room_config.trv_entity_ids:
                trv_state = self.hass.states.get(trv_id)
                if trv_state:
                    hvac_mode = trv_state.state
                    break
            window_state = self._calculate_window_state(window_open)
            self.current_room_data = RoomData(
                room_name=self.room_config.name,
                current_temperature=fused_temp or 20.0,
                main_sensor_temperature=main_temp or 20.0,
                trv_temperatures=trv_temps,
                window_state=window_state,
                outdoor_temperature=outdoor_temp,
                target_temperature=current_target,
                hvac_mode=hvac_mode,
                heating_active=current_target is not None and fused_temp is not None and fused_temp < current_target,
                heating_rate=self._heat_model.get_heating_rate(),
            )
            return self.current_room_data
        except Exception as err:
            _LOGGER.error("Error updating room %s data: %s", self.room_config.name, err)
            raise UpdateFailed(f"Error reading room data: {err}") from err
    def _get_sensor_value(self, entity_id: str | None) -> float | None:
        """Get numeric value from sensor."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None
    def _check_window_state(self, window_entity_ids: list[str]) -> bool:
        """Check if any window is open."""
        if not window_entity_ids:
            return False
        for entity_id in window_entity_ids:
            state = self.hass.states.get(entity_id)
            if state and state.state == "on":
                return True
        return False
    def _calculate_window_state(self, window_open: bool) -> WindowState:
        """Calculate current window state."""
        from datetime import datetime
        if not window_open:
            return WindowState(
                is_open=False,
                heating_should_stop=False,
                reason="window_closed",
            )
        hub_settings = self.get_hub_settings()
        window_timeout = hub_settings.get("global_window_open_timeout", 30)
        return WindowState(
            is_open=True,
            heating_should_stop=True,
            reason="window_open_heating_disabled",
            timeout_active=True,
            last_change=datetime.now(),
        )