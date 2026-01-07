"""DataUpdateCoordinator for TaDIY."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FROST_PROTECTION_TEMP,
    CONF_HUB_MODE,
    DEFAULT_FROST_PROTECTION_TEMP,
    DEFAULT_HUB_MODE,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_KEY_SCHEDULES,
    STORAGE_VERSION,
    STORAGE_VERSION_SCHEDULES,
    UPDATE_INTERVAL,
)
from .core.early_start import HeatUpModel
from .core.schedule import ScheduleEngine
from .core.temperature import SensorReading, calculate_fused_temperature
from .models.room import RoomConfig
from .models.schedule import RoomSchedule

_LOGGER = logging.getLogger(__name__)

# Sensor fusion weights
MAIN_SENSOR_WEIGHT: float = 10.0
TRV_SENSOR_WEIGHT: float = 0.1


class TaDIYDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TaDIY data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config_data: dict,
        rooms: list[dict],
        hub_mode: str = DEFAULT_HUB_MODE,
        frost_protection_temp: float = DEFAULT_FROST_PROTECTION_TEMP,
    ) -> None:
        """Initialize coordinator."""
        self.entry_id = entry_id
        self.config_data = config_data
        self.rooms: list[RoomConfig] = []
        self._heat_models: dict[str, HeatUpModel] = {}
        
        # Hub state
        self._hub_mode = hub_mode
        self._frost_protection_temp = frost_protection_temp
        
        # Schedule engine
        self.schedule_engine = ScheduleEngine(frost_protection_temp)
        
        # Storage
        self._learning_store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}"
        )
        self._schedule_store = Store(
            hass, STORAGE_VERSION_SCHEDULES, f"{STORAGE_KEY_SCHEDULES}_{entry_id}"
        )

        # Override tracking
        self._overrides: dict[str, dict[str, Any]] = {}

        # Initialize rooms
        for room_data in rooms:
            try:
                room = RoomConfig.from_dict(room_data)
                self.rooms.append(room)
                self._heat_models[room.name] = HeatUpModel(room_name=room.name)
                _LOGGER.debug("Loaded room configuration: %s", room.name)
            except (ValueError, KeyError) as err:
                _LOGGER.error("Failed to load room %s: %s", room_data.get("name"), err)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def async_load_learning_data(self) -> None:
        """Load learning data from storage."""
        data = await self._learning_store.async_load()
        if not data:
            _LOGGER.info("No learning data found, starting fresh")
            return

        for room_name, model_data in data.items():
            if room_name in self._heat_models:
                try:
                    self._heat_models[room_name] = HeatUpModel.from_dict(model_data)
                    _LOGGER.debug("Loaded learning data for room: %s", room_name)
                except (ValueError, KeyError) as err:
                    _LOGGER.warning(
                        "Failed to load learning data for %s: %s", room_name, err
                    )

    async def async_save_learning_data(self) -> None:
        """Save learning data to storage."""
        data = {
            name: model.to_dict() for name, model in self._heat_models.items()
        }
        await self._learning_store.async_save(data)
        _LOGGER.debug("Learning data saved")

    async def async_load_schedules(self) -> None:
        """Load schedule data from storage."""
        data = await self._schedule_store.async_load()
        if not data:
            _LOGGER.info("No schedule data found")
            return

        # Load hub settings
        hub_data = data.get("hub", {})
        self._hub_mode = hub_data.get("current_mode", DEFAULT_HUB_MODE)
        self._frost_protection_temp = hub_data.get(
            "frost_protection_temp", DEFAULT_FROST_PROTECTION_TEMP
        )
        self.schedule_engine.set_frost_protection_temp(self._frost_protection_temp)

        # Load room schedules
        rooms_data = data.get("rooms", {})
        for room_name, schedule_data in rooms_data.items():
            try:
                room_schedule = RoomSchedule.from_dict(schedule_data)
                self.schedule_engine.update_room_schedule(room_name, room_schedule)
                _LOGGER.debug("Loaded schedule for room: %s", room_name)
            except (ValueError, KeyError) as err:
                _LOGGER.warning(
                    "Failed to load schedule for %s: %s", room_name, err
                )

    async def async_save_schedules(self) -> None:
        """Save schedule data to storage."""
        # Collect room schedules
        rooms_data = {}
        for room_name in [room.name for room in self.rooms]:
            if room_name in self.schedule_engine._room_schedules:
                room_schedule = self.schedule_engine._room_schedules[room_name]
                rooms_data[room_name] = room_schedule.to_dict()

        data = {
            "hub": {
                "current_mode": self._hub_mode,
                "frost_protection_temp": self._frost_protection_temp,
            },
            "rooms": rooms_data,
        }

        await self._schedule_store.async_save(data)
        _LOGGER.debug("Schedule data saved")

    def get_hub_mode(self) -> str:
        """Get current hub mode."""
        # Try to get from select entity if available
        select_entity_id = f"select.tadiy_hub_mode"
        select_state = self.hass.states.get(select_entity_id)
        
        if select_state and select_state.state in ["normal", "homeoffice", "manual", "off"]:
            self._hub_mode = select_state.state
        
        return self._hub_mode

    def get_frost_protection_temp(self) -> float:
        """Get current frost protection temperature."""
        # Try to get from number entity if available
        number_entity_id = f"number.tadiy_frost_protection"
        number_state = self.hass.states.get(number_entity_id)
        
        if number_state and number_state.state not in ("unknown", "unavailable"):
            try:
                self._frost_protection_temp = float(number_state.state)
            except (ValueError, TypeError):
                pass
        
        return self._frost_protection_temp

    def update_room_schedule(self, room_name: str, schedule: RoomSchedule) -> None:
        """Update schedule for a room."""
        self.schedule_engine.update_room_schedule(room_name, schedule)

    def get_scheduled_target(self, room_name: str) -> float | None:
        """Get scheduled target temperature for a room."""
        mode = self.get_hub_mode()
        return self.schedule_engine.get_target_temperature(room_name, mode)

    def check_override(
        self, room_name: str, current_target: float, scheduled_target: float | None
    ) -> dict[str, Any]:
        """
        Check if current target is an override.
        
        Returns dict with:
            - is_override: bool
            - override_until: datetime | None
        """
        if scheduled_target is None:
            # Manual mode or no schedule
            return {"is_override": False, "override_until": None}

        # Check if temperature differs from schedule
        if abs(current_target - scheduled_target) > 0.1:
            # Override detected - calculate until when
            next_change = self.schedule_engine.get_next_schedule_change(
                room_name, self.get_hub_mode()
            )
            
            override_until = next_change[0] if next_change else None
            
            # Store override info
            self._overrides[room_name] = {
                "active": True,
                "until": override_until,
                "scheduled_target": scheduled_target,
                "override_target": current_target,
            }
            
            return {"is_override": True, "override_until": override_until}
        
        # No override, clear tracking
        if room_name in self._overrides:
            del self._overrides[room_name]
        
        return {"is_override": False, "override_until": None}

    def get_override_info(self, room_name: str) -> dict[str, Any]:
        """Get override information for a room."""
        return self._overrides.get(
            room_name, {"active": False, "until": None}
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors."""
        try:
            data = {}
            current_mode = self.get_hub_mode()
            frost_temp = self.get_frost_protection_temp()

            for room_config in self.rooms:
                room_data = await self._fetch_room_data(room_config, current_mode, frost_temp)
                data[room_config.name] = room_data

            return data

        except Exception as err:
            _LOGGER.error("Error updating TaDIY data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _fetch_room_data(
        self, room_config: RoomConfig, mode: str, frost_temp: float
    ) -> dict[str, Any]:
        """Fetch data for a single room."""
        # Get temperatures
        main_temp = self._get_sensor_value(room_config.main_temp_sensor_id)
        outdoor_temp = self._get_sensor_value(room_config.outdoor_sensor_id)

        # TRV temperatures for fusion
        trv_readings = []
        for trv_id in room_config.trv_entity_ids:
            trv_state = self.hass.states.get(trv_id)
            if trv_state and trv_state.attributes.get("current_temperature"):
                try:
                    trv_temp = float(trv_state.attributes["current_temperature"])
                    trv_readings.append(
                        SensorReading(
                            entity_id=trv_id,
                            temperature=trv_temp,
                            weight=TRV_SENSOR_WEIGHT,
                        )
                    )
                except (ValueError, TypeError):
                    pass

        # Fused temperature calculation
        if main_temp is not None:
            fused_temp = main_temp
            _LOGGER.debug(
                "Room %s: Using Main sensor as fused temp: %.2f°C",
                room_config.name,
                main_temp,
            )
        else:
            if trv_readings:
                fused_temp = calculate_fused_temperature(trv_readings)
                _LOGGER.debug(
                    "Room %s: Main sensor unavailable, using TRV average: %.2f°C",
                    room_config.name,
                    fused_temp,
                )
            else:
                _LOGGER.warning("No valid temperature for room %s", room_config.name)
                fused_temp = None

        # Window state
        window_open = self._check_window_state(room_config.window_sensor_ids)

        # Get scheduled target
        scheduled_target = self.get_scheduled_target(room_config.name)

        # Heating rate from model
        heat_model = self._heat_models.get(room_config.name)
        heating_rate = heat_model.get_heating_rate() if heat_model else None

        return {
            "main_temp": main_temp,
            "outdoor_temp": outdoor_temp,
            "fused_temp": fused_temp,
            "window_open": window_open,
            "scheduled_target": scheduled_target,
            "heating_rate": heating_rate,
            "heat_model": heat_model,
        }

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
