"""Coordinator for TaDIY integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DONT_HEAT_BELOW_OUTDOOR,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_LEARN_HEATING_RATE,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_USE_EARLY_START,
    CONF_WINDOW_CLOSE_TIMEOUT,
    CONF_WINDOW_OPEN_TIMEOUT,
    CONF_WINDOW_SENSORS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_HEATING_RATE,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .core.early_start import EarlyStartCalculator, HeatUpModel
from .core.temperature import SensorReading, calculate_fused_temperature
from .core.window import WindowDetector, WindowState
from .models.room import RoomConfig, RoomData

_LOGGER = logging.getLogger(__name__)

MAIN_SENSOR_WEIGHT: float = 2.0
TRV_SENSOR_WEIGHT: float = 0.5


class TaDIYDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RoomData]]):
    """TaDIY data update coordinator with learning and early start."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: dict[str, Any],
        rooms_config: list[dict],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        
        self.entry_id = entry_id
        self._entry_data = entry_data
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        
        self.rooms: list[RoomConfig] = []
        self._window_detectors: dict[str, WindowDetector] = {}
        self._heat_models: dict[str, HeatUpModel] = {}
        self._early_start_calculators: dict[str, EarlyStartCalculator] = {}
        self._previous_temps: dict[str, float] = {}
        self._previous_update_time: dict[str, Any] = {}
        
        self._initialize_rooms(rooms_config)

    def _initialize_rooms(self, rooms_config: list[dict]) -> None:
        """Initialize room configurations with global defaults."""
        for room_dict in rooms_config:
            try:
                room_config = RoomConfig(
                    name=room_dict.get(CONF_ROOM_NAME, "Unknown"),
                    trv_entity_ids=room_dict.get(CONF_TRV_ENTITIES, []),
                    main_temp_sensor_id=room_dict.get(CONF_MAIN_TEMP_SENSOR, ""),
                    window_sensor_ids=room_dict.get(CONF_WINDOW_SENSORS, []),
                    outdoor_sensor_id=room_dict.get(CONF_OUTDOOR_SENSOR, ""),
                    window_open_timeout=self._get_room_or_global(
                        room_dict,
                        CONF_WINDOW_OPEN_TIMEOUT,
                        CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
                        DEFAULT_WINDOW_OPEN_TIMEOUT,
                    ),
                    window_close_timeout=self._get_room_or_global(
                        room_dict,
                        CONF_WINDOW_CLOSE_TIMEOUT,
                        CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
                        DEFAULT_WINDOW_CLOSE_TIMEOUT,
                    ),
                    dont_heat_below_outdoor=self._get_room_or_global(
                        room_dict,
                        CONF_DONT_HEAT_BELOW_OUTDOOR,
                        CONF_GLOBAL_DONT_HEAT_BELOW,
                        DEFAULT_DONT_HEAT_BELOW,
                    ),
                    use_early_start=self._get_room_or_global(
                        room_dict,
                        CONF_USE_EARLY_START,
                        CONF_GLOBAL_USE_EARLY_START,
                        DEFAULT_USE_EARLY_START,
                    ),
                    learn_heating_rate=self._get_room_or_global(
                        room_dict,
                        CONF_LEARN_HEATING_RATE,
                        CONF_GLOBAL_LEARN_HEATING_RATE,
                        DEFAULT_LEARN_HEATING_RATE,
                    ),
                )
                self.rooms.append(room_config)
                
                self._window_detectors[room_config.name] = WindowDetector(
                    open_timeout_seconds=room_config.window_open_timeout,
                    close_timeout_seconds=room_config.window_close_timeout,
                )
                
                self._heat_models[room_config.name] = HeatUpModel(
                    room_name=room_config.name
                )
                
                self._early_start_calculators[room_config.name] = EarlyStartCalculator(
                    self._heat_models[room_config.name]
                )
                
                _LOGGER.debug("Initialized room: %s", room_config.name)
                
            except Exception as err:
                _LOGGER.error(
                    "Failed to initialize room %s: %s",
                    room_dict.get(CONF_ROOM_NAME),
                    err,
                    exc_info=True,
                )

    def _get_room_or_global(
        self, room_dict: dict, room_key: str, global_key: str, default: Any
    ) -> Any:
        """Get value from room config, fall back to global, then default."""
        if room_key in room_dict and room_dict[room_key] is not None:
            return room_dict[room_key]
        return self._entry_data.get(global_key, default)

    async def async_load_learning_data(self) -> None:
        """Load learning data from storage."""
        try:
            data = await self._store.async_load()
            if data and "heat_models" in data:
                for room_name, model_data in data["heat_models"].items():
                    if room_name in self._heat_models:
                        self._heat_models[room_name] = HeatUpModel.from_dict(model_data)
                        self._early_start_calculators[room_name] = EarlyStartCalculator(
                            self._heat_models[room_name]
                        )
                _LOGGER.info("Loaded learning data for %d rooms", len(data["heat_models"]))
        except Exception as err:
            _LOGGER.warning("Could not load learning data: %s", err)

    async def async_save_learning_data(self) -> None:
        """Save learning data to storage."""
        try:
            data = {
                "heat_models": {
                    name: model.to_dict()
                    for name, model in self._heat_models.items()
                }
            }
            await self._store.async_save(data)
            _LOGGER.debug("Saved learning data for %d rooms", len(self._heat_models))
        except Exception as err:
            _LOGGER.error("Could not save learning data: %s", err)

    async def _async_update_data(self) -> dict[str, RoomData]:
        """Fetch data from sensors and create RoomData objects."""
        try:
            room_data_dict: dict[str, RoomData] = {}
            
            for room_config in self.rooms:
                try:
                    room_data = await self._fetch_room_data(room_config)
                    if room_data:
                        room_data_dict[room_config.name] = room_data
                        
                        if room_config.learn_heating_rate:
                            await self._update_learning(room_config.name, room_data)
                except Exception as err:
                    _LOGGER.error(
                        "Failed to fetch data for room %s: %s",
                        room_config.name,
                        err,
                        exc_info=True,
                    )
            
            return room_data_dict
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching TaDIY data: {err}") from err

    async def _fetch_room_data(self, room_config: RoomConfig) -> RoomData | None:
        """Fetch data for a single room and create RoomData object."""
        main_temp = self._get_sensor_value(room_config.main_temp_sensor_id)
        
        trv_temps: list[float] = []
        trv_readings: list[SensorReading] = []
        
        for trv_entity in room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_entity)
            if trv_state and trv_state.state not in ("unknown", "unavailable"):
                try:
                    temp = float(
                        trv_state.attributes.get("current_temperature", trv_state.state)
                    )
                    trv_temps.append(temp)
                    trv_readings.append(
                        SensorReading(
                            entity_id=trv_entity,
                            temperature=temp,
                            weight=TRV_SENSOR_WEIGHT,
                        )
                    )
                except (ValueError, TypeError, KeyError) as err:
                    _LOGGER.debug(
                        "Could not read temperature from %s: %s", trv_entity, err
                    )

        all_readings = []
        if main_temp is not None:
            all_readings.append(
                SensorReading(
                    entity_id=room_config.main_temp_sensor_id,
                    temperature=main_temp,
                    weight=MAIN_SENSOR_WEIGHT,
                )
            )
        all_readings.extend(trv_readings)
        
        fused_temp = calculate_fused_temperature(all_readings)
        if fused_temp is None:
            _LOGGER.warning("No valid temperature for room %s", room_config.name)
            return None

        outdoor_temp = None
        if room_config.outdoor_sensor_id:
            outdoor_temp = self._get_sensor_value(room_config.outdoor_sensor_id)

        window_open_raw = False
        if room_config.window_sensor_ids:
            for sensor in room_config.window_sensor_ids:
                sensor_state = self.hass.states.get(sensor)
                if sensor_state and sensor_state.state == "on":
                    window_open_raw = True
                    break

        raw_window_state = WindowState(
            is_open=window_open_raw,
            reason="sensor" if room_config.window_sensor_ids else "no_sensors",
        )
        
        window_detector = self._window_detectors.get(room_config.name)
        window_state = (
            window_detector.update(raw_window_state)
            if window_detector
            else raw_window_state
        )

        target_temp = None
        hvac_mode = "heat"
        for trv_entity in room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_entity)
            if trv_state:
                target_temp = trv_state.attributes.get("temperature")
                hvac_mode = (
                    trv_state.state
                    if trv_state.state in ("heat", "off")
                    else "heat"
                )
                break

        heating_active = hvac_mode == "heat" and not window_state.heating_should_stop
        
        heat_model = self._heat_models.get(room_config.name)
        heating_rate = (
            heat_model.degrees_per_hour
            if heat_model
            else DEFAULT_HEATING_RATE
        )

        return RoomData(
            room_name=room_config.name,
            current_temperature=fused_temp,
            main_sensor_temperature=main_temp if main_temp else fused_temp,
            trv_temperatures=trv_temps,
            window_state=window_state,
            outdoor_temperature=outdoor_temp,
            target_temperature=target_temp,
            hvac_mode=hvac_mode,
            last_update=dt_util.utcnow(),
            heating_active=heating_active,
            heating_rate=heating_rate,
        )

    def _get_sensor_value(self, entity_id: str) -> float | None:
        """Get numeric value from sensor."""
        if not entity_id:
            return None
            
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except (ValueError, TypeError) as err:
                _LOGGER.debug("Could not convert sensor value: %s", err)
        return None

    async def _update_learning(self, room_name: str, room_data: RoomData) -> None:
        """Update heating rate learning for a room."""
        if not room_data.heating_active or room_data.target_temperature is None:
            return

        current_temp = room_data.current_temperature
        prev_temp = self._previous_temps.get(room_name)
        prev_time = self._previous_update_time.get(room_name)

        if prev_temp is not None and prev_time is not None:
            now = dt_util.utcnow()
            time_diff = (now - prev_time).total_seconds() / 60
            
            if time_diff > 0 and current_temp > prev_temp:
                temp_increase = current_temp - prev_temp
                heat_model = self._heat_models.get(room_name)
                if heat_model:
                    heat_model.update_with_measurement(temp_increase, time_diff)
                    
                    if heat_model.sample_count > 0 and heat_model.sample_count % 10 == 0:
                        await self.async_save_learning_data()
                        _LOGGER.debug(
                            "Learning update for %s: %.2f°C/h (%d samples)",
                            room_name,
                            heat_model.degrees_per_hour,
                            heat_model.sample_count,
                        )

        self._previous_temps[room_name] = current_temp
        self._previous_update_time[room_name] = dt_util.utcnow()
