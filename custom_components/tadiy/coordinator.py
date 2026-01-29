"""Coordinators for TaDIY integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .core.logger import TaDIYLogger
from .core.sensor_manager import SensorManager
from .core.trv_manager import TrvManager
from .core.orchestrator import RoomOrchestrator

from .const import (
    CONF_CUSTOM_MODES,
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_EARLY_START_MAX,
    CONF_GLOBAL_EARLY_START_OFFSET,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_OVERRIDE_TIMEOUT,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    CONF_HEATING_CURVE_SLOPE,
    CONF_HUMIDITY_SENSOR,
    CONF_HYSTERESIS,
    CONF_LOCATION_MODE_ENABLED,
    CONF_MAIN_TEMP_SENSOR,
    CONF_OUTDOOR_SENSOR,
    CONF_PERSON_ENTITIES,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_ROOM_NAME,
    CONF_TRV_ENTITIES,
    CONF_USE_HEATING_CURVE,
    CONF_USE_HVAC_OFF_FOR_LOW_TEMP,
    CONF_USE_PID_CONTROL,
    CONF_USE_WEATHER_PREDICTION,
    CONF_ADJACENT_ROOMS,
    CONF_USE_ROOM_COUPLING,
    CONF_COUPLING_STRENGTH,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    CONF_DEBUG_ROOMS,
    CONF_DEBUG_HUB,
    CONF_DEBUG_PANEL,
    CONF_DEBUG_UI,
    CONF_DEBUG_CARDS,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_FROST_PROTECTION_TEMP,
    DEFAULT_GLOBAL_OVERRIDE_TIMEOUT,
    DEFAULT_HEATING_CURVE_SLOPE,
    DEFAULT_HUB_MODE,
    DEFAULT_HUB_MODES,
    DEFAULT_HYSTERESIS,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_USE_EARLY_START,
    DEFAULT_USE_HEATING_CURVE,
    DEFAULT_USE_HVAC_OFF_FOR_LOW_TEMP,
    DEFAULT_USE_PID_CONTROL,
    DEFAULT_USE_WEATHER_PREDICTION,
    DEFAULT_USE_ROOM_COUPLING,
    DEFAULT_COUPLING_STRENGTH,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    MAX_CUSTOM_MODES,
    OVERRIDE_TIMEOUT_ALWAYS,
    OVERRIDE_TIMEOUT_NEVER,
    STORAGE_KEY,
    STORAGE_KEY_SCHEDULES,
    STORAGE_VERSION,
    STORAGE_VERSION_SCHEDULES,
    UPDATE_INTERVAL,
)
from .core.control import HeatingController, PIDConfig, PIDHeatingController
from .core.early_start import HeatUpModel
from .core.heating_curve import HeatingCurve, HeatingCurveConfig
from .core.location import LocationManager
from .core.override import OverrideManager
from .core.room import RoomConfig, RoomData
from .core.schedule import ScheduleEngine
from .core.weather_predictor import WeatherPredictor
from .core.room_coupling import RoomCouplingManager
from .core.window import WindowState

_LOGGER = logging.getLogger(__name__)

# Sensor fusion weights
MAIN_SENSOR_WEIGHT: float = 10.0
TRV_SENSOR_WEIGHT: float = 0.1


class TaDIYHubCoordinator(DataUpdateCoordinator):
    """Coordinator for TaDIY Hub (global configuration)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config_data: dict[str, Any],
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the hub coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="TaDIY Hub",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry_id = entry_id
        self.config_entry = config_entry
        self.config_data = config_data

        # Hub state
        self.hub_mode = DEFAULT_HUB_MODE
        self.frost_protection_temp = DEFAULT_FROST_PROTECTION_TEMP

        # Custom modes: Start with defaults, load additional from config
        self.custom_modes = list(DEFAULT_HUB_MODES)
        additional_modes = config_data.get(CONF_CUSTOM_MODES, [])
        for mode in additional_modes:
            if mode not in self.custom_modes:
                self.custom_modes.append(mode)

        # Global settings for room coordinators
        self.global_settings: dict[str, Any] = {
            CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: config_data.get(
                CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
            ),
            CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: config_data.get(
                CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
            ),
            CONF_GLOBAL_DONT_HEAT_BELOW: config_data.get(
                CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW
            ),
            CONF_GLOBAL_USE_EARLY_START: config_data.get(
                CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START
            ),
            CONF_GLOBAL_LEARN_HEATING_RATE: config_data.get(
                CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
            ),
            CONF_GLOBAL_EARLY_START_OFFSET: config_data.get(
                CONF_GLOBAL_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET
            ),
            CONF_GLOBAL_EARLY_START_MAX: config_data.get(
                CONF_GLOBAL_EARLY_START_MAX, DEFAULT_EARLY_START_MAX
            ),
            CONF_GLOBAL_OVERRIDE_TIMEOUT: config_data.get(
                CONF_GLOBAL_OVERRIDE_TIMEOUT, DEFAULT_GLOBAL_OVERRIDE_TIMEOUT
            ),
        }

        # Storage
        self.learning_store = Store(
            hass,
            STORAGE_VERSION,
            "{}_{}".format(STORAGE_KEY, entry_id),
        )
        self.schedule_store = Store(
            hass,
            STORAGE_VERSION_SCHEDULES,
            "{}_{}".format(STORAGE_KEY_SCHEDULES, entry_id),
        )

        # Overrides tracking
        self.overrides: dict[str, dict[str, Any]] = {}

        # Heat models
        self.heat_models: dict[str, Any] = {}

        # Schedule engine
        self.schedule_engine: Any = None

        # Location-based control
        self.location_mode_enabled = config_data.get(CONF_LOCATION_MODE_ENABLED, False)
        person_entities = config_data.get(CONF_PERSON_ENTITIES, [])
        self.location_manager = LocationManager(hass, person_entities)

        self.data = {
            "hub": True,
            "name": config_data.get("name", "TaDIY Hub"),
            "hub_mode": self.hub_mode,
            "frost_protection_temp": self.frost_protection_temp,
        }

        # Weather Predictor (Phase 3.3)
        weather_entity = config_data.get(CONF_WEATHER_ENTITY)
        if weather_entity:
            self.weather_predictor = WeatherPredictor(hass, weather_entity)
            _LOGGER.info(
                "Weather predictor initialized with entity: %s", weather_entity
            )
        else:
            self.weather_predictor: WeatherPredictor | None = None

        # Weather update tracking
        self._last_weather_update: dt_util.dt.datetime | None = None
        self._weather_update_interval = timedelta(minutes=30)

        # Room Coupling Manager (Phase 3.2)
        self.room_coupling_manager = RoomCouplingManager()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from coordinator."""
        try:
            # Hub coordinator holds global config
            self._update_hub_mode()
            self._update_frost_protection_temp()

            # Update location state if location mode enabled
            if self.location_mode_enabled:
                location_state = self.location_manager.update_location_state()
                _LOGGER.debug(
                    "Location state: %d/%d persons home",
                    location_state.person_count_home,
                    location_state.person_count_total,
                )
            self._update_global_settings()

            # Update weather forecast periodically (every 30 min)
            await self._update_weather_forecast()

            # Build data dict
            data_dict = {
                "hub": True,
                "name": self.config_data.get("name", "TaDIY Hub"),
                "hub_mode": self.hub_mode,
                "frost_protection_temp": self.frost_protection_temp,
            }

            # Add location status if location mode enabled
            if self.location_mode_enabled:
                location_state = self.location_manager.get_location_state()
                if location_state.anyone_home:
                    location_status = f"{location_state.person_count_home}/{location_state.person_count_total} Home"
                else:
                    location_status = "Away (nobody home)"

                data_dict["location_status"] = location_status
                data_dict["location_attributes"] = {
                    "anyone_home": location_state.anyone_home,
                    "person_count_home": location_state.person_count_home,
                    "person_count_total": location_state.person_count_total,
                    "persons_home": location_state.persons_home,
                    "persons_away": location_state.persons_away,
                    "last_updated": location_state.last_updated.isoformat(),
                }
            else:
                data_dict["location_status"] = "Disabled"
                data_dict["location_attributes"] = {}

            self.data.update(data_dict)

            # Add weather prediction data if available
            if self.weather_predictor:
                weather_summary = self.weather_predictor.get_forecast_summary()
                self.data["weather_prediction"] = weather_summary

            return self.data
        except Exception as err:
            raise UpdateFailed("Error updating TaDIY Hub: {}".format(err)) from err

    def _update_global_settings(self) -> None:
        """Update global settings from config_data."""
        self.global_settings.update(
            {
                CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: self.config_data.get(
                    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT, DEFAULT_WINDOW_OPEN_TIMEOUT
                ),
                CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: self.config_data.get(
                    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT, DEFAULT_WINDOW_CLOSE_TIMEOUT
                ),
                CONF_GLOBAL_DONT_HEAT_BELOW: self.config_data.get(
                    CONF_GLOBAL_DONT_HEAT_BELOW, DEFAULT_DONT_HEAT_BELOW
                ),
                CONF_GLOBAL_USE_EARLY_START: self.config_data.get(
                    CONF_GLOBAL_USE_EARLY_START, DEFAULT_USE_EARLY_START
                ),
                CONF_GLOBAL_LEARN_HEATING_RATE: self.config_data.get(
                    CONF_GLOBAL_LEARN_HEATING_RATE, DEFAULT_LEARN_HEATING_RATE
                ),
                CONF_GLOBAL_EARLY_START_OFFSET: self.config_data.get(
                    CONF_GLOBAL_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET
                ),
                CONF_GLOBAL_EARLY_START_MAX: self.config_data.get(
                    CONF_GLOBAL_EARLY_START_MAX, DEFAULT_EARLY_START_MAX
                ),
                CONF_GLOBAL_OVERRIDE_TIMEOUT: self.config_data.get(
                    CONF_GLOBAL_OVERRIDE_TIMEOUT, DEFAULT_GLOBAL_OVERRIDE_TIMEOUT
                ),
            }
        )

    def _update_hub_mode(self) -> None:
        """Update hub mode from select entity if available."""
        select_entity_id = "select.{}_hub_mode".format(DOMAIN)
        select_state = self.hass.states.get(select_entity_id)

        if select_state and select_state.state not in ("unknown", "unavailable"):
            # Accept any mode that's in the custom_modes list (includes manual, off)
            if select_state.state in self.custom_modes:
                self.hub_mode = select_state.state
                _LOGGER.debug("Hub mode updated to: %s", self.hub_mode)

    def _update_frost_protection_temp(self) -> None:
        """Update frost protection temperature from number entity if available."""
        number_entity_id = "number.{}_frost_protection".format(DOMAIN)
        number_state = self.hass.states.get(number_entity_id)

        if number_state and number_state.state not in ("unknown", "unavailable"):
            try:
                temp = float(number_state.state)
                self.frost_protection_temp = temp
                _LOGGER.debug("Frost protection temp updated to: %.1f°C", temp)
            except (ValueError, TypeError):
                pass

    async def async_load_schedules(self) -> None:
        """Load and parse schedules from storage."""
        _LOGGER.debug("Loading schedules for TaDIY Hub")

        data = await self.schedule_store.async_load()

        if not data:
            _LOGGER.info("No schedule data found, starting fresh")
            return

        try:
            hub_data = data.get("hub", {})
            self.hub_mode = hub_data.get("current_mode", DEFAULT_HUB_MODE)
            self.frost_protection_temp = hub_data.get(
                "frost_protection_temp",
                DEFAULT_FROST_PROTECTION_TEMP,
            )

            # Load custom modes
            saved_modes = hub_data.get("custom_modes", [])
            if saved_modes:
                # Merge with defaults (ensure defaults are always present)
                self.custom_modes = list(DEFAULT_HUB_MODES)
                for mode in saved_modes:
                    if mode not in self.custom_modes:
                        self.custom_modes.append(mode)
                _LOGGER.debug("Loaded custom modes: %s", self.custom_modes)

            if self.schedule_engine:
                self.schedule_engine.set_frost_protection_temp(
                    self.frost_protection_temp
                )

            _LOGGER.info("Schedules loaded successfully")
        except Exception as err:
            _LOGGER.error("Failed to load schedules: %s", err)

    async def async_save_schedules(self) -> None:
        """Save schedule data to storage."""
        _LOGGER.debug("Saving schedules for TaDIY Hub")

        try:
            data = {
                "hub": {
                    "current_mode": self.hub_mode,
                    "frost_protection_temp": self.frost_protection_temp,
                    "custom_modes": self.custom_modes,
                },
                "rooms": {},
            }

            await self.schedule_store.async_save(data)
            _LOGGER.info("Schedules saved successfully")
        except Exception as err:
            _LOGGER.error("Failed to save schedules: %s", err)

    async def async_load_learning_data(self) -> None:
        """Load learning data from storage."""
        _LOGGER.debug("Loading learning data for TaDIY Hub")

        data = await self.learning_store.async_load()

        if not data:
            _LOGGER.info("No learning data found, starting fresh")
            return

        try:
            for room_name, model_data in data.items():
                if room_name in self.heat_models:
                    self.heat_models[room_name] = model_data
                    _LOGGER.debug("Loaded learning data for room: %s", room_name)
        except Exception as err:
            _LOGGER.error("Failed to load learning data: %s", err)

    async def async_save_learning_data(self) -> None:
        """Save learning data to storage."""
        _LOGGER.debug("Saving learning data for TaDIY Hub")

        try:
            await self.learning_store.async_save(self.heat_models)
            _LOGGER.info("Learning data saved successfully")
        except Exception as err:
            _LOGGER.error("Failed to save learning data: %s", err)

    def get_hub_mode(self) -> str:
        """Get current hub mode."""
        self._update_hub_mode()
        return self.hub_mode

    def set_hub_mode(self, mode: str) -> None:
        """Set hub mode and clear all room overrides."""
        if mode in self.custom_modes:
            old_mode = self.hub_mode
            self.hub_mode = mode
            _LOGGER.debug("Hub mode set to: %s", mode)
            
            # Clear all room overrides on mode change
            if old_mode != mode:
                self._clear_all_room_overrides()
        else:
            _LOGGER.warning(
                "Invalid hub mode: %s (available: %s)", mode, self.custom_modes
            )

    def _clear_all_room_overrides(self) -> None:
        """Clear overrides in all room coordinators on mode change."""
        from . import DOMAIN
        
        count = 0
        for entry_id, entry_data in self.hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and entry_data.get("type") == "room":
                coordinator = entry_data.get("coordinator")
                if coordinator and hasattr(coordinator, "override_manager"):
                    cleared = coordinator.override_manager.clear_all_overrides()
                    count += cleared
                    if cleared > 0:
                        # Persist the cleared state
                        self.hass.async_create_task(coordinator.async_save_overrides())
        
        if count > 0:
            _LOGGER.info("Mode change: Cleared %d override(s) across all rooms", count)


    def get_custom_modes(self) -> list[str]:
        """Get list of available custom modes."""
        return self.custom_modes

    def add_custom_mode(self, mode: str) -> bool:
        """Add a custom mode. Returns True if added, False if already exists or invalid."""
        # Check if mode name is valid
        if not mode or not mode.strip():
            _LOGGER.warning("Cannot add mode: empty name")
            return False

        mode = mode.strip().lower()

        # Check if it's a default mode
        if mode in DEFAULT_HUB_MODES:
            _LOGGER.warning("Cannot add mode: %s (is default mode)", mode)
            return False

        # Check if mode already exists
        if mode in self.custom_modes:
            _LOGGER.warning("Cannot add mode: %s (already exists)", mode)
            return False

        # Check limit
        if len(self.custom_modes) >= MAX_CUSTOM_MODES:
            _LOGGER.warning(
                "Cannot add mode: %s (limit of %d modes reached)",
                mode,
                MAX_CUSTOM_MODES,
            )
            return False

        self.custom_modes.append(mode)
        _LOGGER.info("Added custom mode: %s", mode)
        return True

    def remove_custom_mode(self, mode: str) -> bool:
        """Remove a custom mode. Returns True if removed, False if not found or is default."""
        if mode in DEFAULT_HUB_MODES:
            _LOGGER.warning("Cannot remove default mode: %s", mode)
            return False
        if mode in self.custom_modes:
            self.custom_modes.remove(mode)
            _LOGGER.info("Removed custom mode: %s", mode)
            return True
        return False

    def get_frost_protection_temp(self) -> float:
        """Get current frost protection temperature."""
        self._update_frost_protection_temp()
        return self.frost_protection_temp

    def set_frost_protection_temp(self, temp: float) -> None:
        """Set frost protection temperature."""
        if -10 <= temp <= 35:
            self.frost_protection_temp = temp
            if self.schedule_engine:
                self.schedule_engine.set_frost_protection_temp(temp)
            _LOGGER.debug("Frost protection temp set to: %.1f°C", temp)
        else:
            _LOGGER.warning("Invalid frost protection temp: %.1f°C", temp)

    def get_override_info(self, room_name: str) -> dict[str, Any]:
        """Get override information for a room."""
        return self.overrides.get(
            room_name,
            {"active": False, "until": None},
        )

    def set_override(self, room_name: str, override_data: dict[str, Any]) -> None:
        """Set override for a room."""
        self.overrides[room_name] = override_data
        _LOGGER.debug("Override set for room %s: %s", room_name, override_data)

    def clear_override(self, room_name: str) -> None:
        """Clear override for a room."""
        if room_name in self.overrides:
            del self.overrides[room_name]
            _LOGGER.debug("Override cleared for room %s", room_name)

    def get_location_state(self):
        """Get current location state."""
        return self.location_manager.get_location_state()

    def is_location_mode_enabled(self) -> bool:
        """Check if location mode is enabled."""
        return self.location_mode_enabled

    def is_away_mode_active(self) -> bool:
        """Check if away mode is active (nobody home)."""
        if not self.location_mode_enabled:
            return False
        return self.location_manager.is_away_mode_active()

    def should_reduce_heating_for_away(self) -> bool:
        """Check if heating should be reduced due to away mode."""
        if not self.location_mode_enabled:
            return False
        return self.location_manager.should_reduce_heating()

    def set_location_override(self, override: bool | None) -> None:
        """Set manual location override."""
        self.location_manager.set_manual_override(override)

    def register_heat_model(self, room_name: str, model: Any) -> None:
        """Register a heat model for a room."""
        self.heat_models[room_name] = model
        _LOGGER.debug("Heat model registered for room: %s", room_name)

    def get_heat_model(self, room_name: str) -> Any | None:
        """Get heat model for a room."""
        return self.heat_models.get(room_name)

    async def _update_weather_forecast(self) -> None:
        """Update weather forecast if interval has passed."""
        if not self.weather_predictor:
            return

        now = dt_util.utcnow()
        if (
            self._last_weather_update is None
            or (now - self._last_weather_update) >= self._weather_update_interval
        ):
            success = await self.weather_predictor.async_update_forecast()
            if success:
                self._last_weather_update = now
                _LOGGER.debug("Weather forecast updated successfully")

    async def async_refresh_weather_forecast(self) -> bool:
        """Manually refresh weather forecast (for service call)."""
        if not self.weather_predictor:
            _LOGGER.warning("No weather entity configured for weather prediction")
            return False

        success = await self.weather_predictor.async_update_forecast()
        if success:
            self._last_weather_update = dt_util.utcnow()
            _LOGGER.info("Weather forecast manually refreshed")
        return success

    def get_weather_adjustment(self, outdoor_temp: float) -> float:
        """
        Get weather-based temperature adjustment.

        Args:
            outdoor_temp: Current outdoor temperature in °C

        Returns:
            Temperature adjustment in °C (positive = increase target, negative = decrease)
        """
        if not self.weather_predictor:
            return 0.0

        prediction = self.weather_predictor.predict_heating_adjustment(outdoor_temp)
        return prediction.adjustment_celsius

    def get_weather_prediction_status(self) -> dict[str, Any]:
        """Get current weather prediction status for sensors."""
        if not self.weather_predictor:
            return {
                "available": False,
                "event": "unknown",
                "adjustment": 0.0,
                "recommendation": "maintain",
            }

        # Get outdoor temp from cached data if available
        outdoor_temp = 10.0  # Default fallback
        weather_state = self.hass.states.get(self.weather_predictor.weather_entity_id)
        if weather_state:
            try:
                outdoor_temp = float(weather_state.attributes.get("temperature", 10.0))
            except (ValueError, TypeError):
                pass

        prediction = self.weather_predictor.predict_heating_adjustment(outdoor_temp)
        summary = self.weather_predictor.get_forecast_summary()

        return {
            "available": summary.get("available", False),
            "event": prediction.predicted_event,
            "adjustment": prediction.adjustment_celsius,
            "recommendation": prediction.recommendation,
            "temperature_change": prediction.temperature_change,
            "event_time": prediction.event_time.isoformat()
            if prediction.event_time
            else None,
            "trend": summary.get("trend", "stable"),
            "forecast_points": summary.get("forecast_points", 0),
        }


class TaDIYRoomCoordinator(DataUpdateCoordinator):
    """Room Coordinator for individual room management."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        room_data: dict[str, Any],
        hub_coordinator: TaDIYHubCoordinator | None = None,
    ) -> None:
        """Initialize Room Coordinator."""
        self.entry_id = entry_id
        self.hass = hass
        self.hub_coordinator = hub_coordinator

        # Initialize Logger
        debug_config = {}
        if hub_coordinator:
            hub_conf = hub_coordinator.config_entry.data
            debug_config = {
                CONF_DEBUG_ROOMS: hub_conf.get(CONF_DEBUG_ROOMS, False),
                CONF_DEBUG_HUB: hub_conf.get(CONF_DEBUG_HUB, False),
                CONF_DEBUG_PANEL: hub_conf.get(CONF_DEBUG_PANEL, False),
                CONF_DEBUG_UI: hub_conf.get(CONF_DEBUG_UI, False),
                CONF_DEBUG_CARDS: hub_conf.get(CONF_DEBUG_CARDS, False),
            }
        self._logger = TaDIYLogger(debug_config)

        # Transform config flow data to RoomConfig format
        room_config_data = self._transform_config_data(room_data)
        self.room_config = RoomConfig.from_dict(room_config_data)

        self.current_room_data: RoomData | None = None
        self._heat_model = HeatUpModel(room_name=self.room_config.name)

        # Thermal Mass Model for cooling rate learning
        from .core.thermal_mass import ThermalMassModel

        self._thermal_mass_model = ThermalMassModel(room_name=self.room_config.name)
        self.thermal_mass_store = Store(
            hass,
            STORAGE_VERSION,
            f"tadiy_thermal_mass_{entry_id}",
        )

        # PID Auto-Tuner
        from .core.pid_tuning import PIDAutoTuner

        self.pid_autotuner = PIDAutoTuner(room_name=self.room_config.name)

        self.schedule_engine = ScheduleEngine()
        self.schedule_store = Store(
            hass,
            STORAGE_VERSION_SCHEDULES,
            STORAGE_KEY_SCHEDULES + "_" + entry_id,
        )
        self._boosts: dict[str, Any] = {}
        self._update_count = 0  # Track updates to suppress initial warnings

        # TRV Calibration Manager
        from .core.calibration import CalibrationManager

        self.calibration_manager = CalibrationManager()
        self.calibration_store = Store(
            hass,
            STORAGE_VERSION,
            f"tadiy_calibrations_{entry_id}",
        )

        # Overshoot Learning Manager
        from .core.overshoot import OvershootManager

        self.overshoot_manager = OvershootManager()
        self.overshoot_store = Store(
            hass,
            STORAGE_VERSION,
            f"tadiy_overshoot_{entry_id}",
        )

        # Override Manager
        self.override_manager = OverrideManager()
        self.override_store = Store(
            hass,
            STORAGE_VERSION,
            f"tadiy_overrides_{entry_id}",
        )

        self.sensor_manager = SensorManager(self)
        self.trv_manager = TrvManager(self)
        self.orchestrator = RoomOrchestrator(self)
        # self._logger is already initialized at the start of __init__
        self._state_listeners = []
        self._last_trv_targets: dict[str, float] = {}

        # Command and Remember: Store the last target TaDIY commanded
        self._commanded_target: float | None = None
        self._commanded_hvac_mode: str = "heat"

        # Cached outdoor temperature for heating curve
        self._cached_outdoor_temp: float | None = None

        # Heating Controller with Hysteresis and optional PID
        hysteresis = room_data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        use_pid = room_data.get(CONF_USE_PID_CONTROL, DEFAULT_USE_PID_CONTROL)

        if use_pid:
            pid_config = PIDConfig(
                kp=room_data.get(CONF_PID_KP, DEFAULT_PID_KP),
                ki=room_data.get(CONF_PID_KI, DEFAULT_PID_KI),
                kd=room_data.get(CONF_PID_KD, DEFAULT_PID_KD),
            )
            self.heating_controller = PIDHeatingController(pid_config)
            self.heating_controller.set_hysteresis(hysteresis)
            _LOGGER.info(
                "Initialized PID controller for room %s (Kp=%.2f, Ki=%.3f, Kd=%.2f, hysteresis=%.2f°C)",
                self.room_config.name,
                pid_config.kp,
                pid_config.ki,
                pid_config.kd,
                hysteresis,
            )
        else:
            self.heating_controller = HeatingController(hysteresis=hysteresis)
            _LOGGER.debug(
                "Initialized basic controller for room %s (hysteresis=%.2f°C)",
                self.room_config.name,
                hysteresis,
            )

        # Heating Curve (optional weather compensation)
        use_curve = room_data.get(CONF_USE_HEATING_CURVE, DEFAULT_USE_HEATING_CURVE)
        if use_curve:
            curve_config = HeatingCurveConfig(
                curve_slope=room_data.get(
                    CONF_HEATING_CURVE_SLOPE, DEFAULT_HEATING_CURVE_SLOPE
                ),
            )
            self.heating_curve = HeatingCurve(curve_config)
            _LOGGER.info(
                "Initialized heating curve for room %s (slope=%.2f)",
                self.room_config.name,
                curve_config.curve_slope,
            )
        else:
            self.heating_curve = None

        # Feature Settings Store
        self.feature_store = Store(
            hass,
            STORAGE_VERSION,
            f"tadiy_features_{entry_id}",
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN + "_room_" + self.room_config.name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        # Register with room coupling manager (Phase 3.2)
        if (
            self.hub_coordinator
            and self.room_config.use_room_coupling
            and self.room_config.adjacent_rooms
        ):
            self.hub_coordinator.room_coupling_manager.register_room(
                room_name=self.room_config.name,
                adjacent_rooms=self.room_config.adjacent_rooms,
                coupling_strength=self.room_config.coupling_strength,
            )

    def debug(self, category: str, message: str, *args: Any) -> None:
        """Log debug message if category enabled."""
        self._logger.debug(category, message, *args)

    def notify_user_interaction(self) -> None:
        """Notify orchestrator of user interactive change."""
        self.orchestrator.notify_user_interaction()

    def _transform_config_data(self, room_data: dict[str, Any]) -> dict[str, Any]:
        """Transform config flow data to RoomConfig expected format."""
        return {
            "name": room_data.get(CONF_ROOM_NAME, "Unknown"),
            "trv_entity_ids": room_data.get(CONF_TRV_ENTITIES, []),
            "main_temp_sensor_id": room_data.get(CONF_MAIN_TEMP_SENSOR, ""),
            "humidity_sensor_id": room_data.get(CONF_HUMIDITY_SENSOR, ""),
            "window_sensor_ids": room_data.get(CONF_WINDOW_SENSORS, []),
            "outdoor_sensor_id": room_data.get(CONF_OUTDOOR_SENSOR, ""),
            "weather_entity_id": room_data.get(CONF_WEATHER_ENTITY, ""),
            "window_open_timeout": room_data.get("window_open_timeout", 300),
            "window_close_timeout": room_data.get("window_close_timeout", 180),
            "dont_heat_below_outdoor": room_data.get("dont_heat_below_outdoor", 0.0),
            "use_early_start": room_data.get("use_early_start", True),
            "learn_heating_rate": room_data.get("learn_heating_rate", True),
            "early_start_offset": room_data.get("early_start_offset"),  # None = use hub
            "early_start_max": room_data.get("early_start_max"),  # None = use hub
            "override_timeout": room_data.get("override_timeout"),  # None = use hub
            "hysteresis": room_data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
            "use_pid_control": room_data.get(
                CONF_USE_PID_CONTROL, DEFAULT_USE_PID_CONTROL
            ),
            "pid_kp": room_data.get(CONF_PID_KP, DEFAULT_PID_KP),
            "pid_ki": room_data.get(CONF_PID_KI, DEFAULT_PID_KI),
            "pid_kd": room_data.get(CONF_PID_KD, DEFAULT_PID_KD),
            "use_heating_curve": room_data.get(
                CONF_USE_HEATING_CURVE, DEFAULT_USE_HEATING_CURVE
            ),
            "heating_curve_slope": room_data.get(
                CONF_HEATING_CURVE_SLOPE, DEFAULT_HEATING_CURVE_SLOPE
            ),
            "use_humidity_compensation": room_data.get(
                "use_humidity_compensation", False
            ),
            "use_hvac_off_for_low_temp": room_data.get(
                CONF_USE_HVAC_OFF_FOR_LOW_TEMP, DEFAULT_USE_HVAC_OFF_FOR_LOW_TEMP
            ),
            "use_weather_prediction": room_data.get(
                CONF_USE_WEATHER_PREDICTION, DEFAULT_USE_WEATHER_PREDICTION
            ),
            "use_room_coupling": room_data.get(
                CONF_USE_ROOM_COUPLING, DEFAULT_USE_ROOM_COUPLING
            ),
            "adjacent_rooms": room_data.get(CONF_ADJACENT_ROOMS, []),
            "coupling_strength": room_data.get(
                CONF_COUPLING_STRENGTH, DEFAULT_COUPLING_STRENGTH
            ),
        }

    async def async_load_schedules(self) -> None:
        """Load room schedules from storage."""
        data = await self.schedule_store.async_load()
        if not data:
            _LOGGER.info(
                "No schedule data found for room: %s - creating default schedule",
                self.room_config.name,
            )
            # Create default schedule so heating works out of the box
            await self._create_default_schedule()
            return

        try:
            from .core.schedule_model import RoomSchedule

            room_schedule = RoomSchedule.from_dict(data)
            self.schedule_engine.update_room_schedule(
                self.room_config.name, room_schedule
            )
            _LOGGER.debug("Loaded schedule for room: %s", self.room_config.name)
        except (ValueError, KeyError) as err:
            _LOGGER.warning(
                "Failed to load schedule for %s: %s - creating default schedule",
                self.room_config.name,
                err,
            )
            await self._create_default_schedule()

    async def _create_default_schedule(self) -> None:
        """Create and save a default schedule for the room."""
        from .core.schedule_model import DaySchedule, RoomSchedule, ScheduleBlock
        from .const import (
            SCHEDULE_TYPE_WEEKDAY,
            SCHEDULE_TYPE_WEEKEND,
            SCHEDULE_TYPE_DAILY,
        )
        from datetime import time

        # Default weekday schedule: 00:00-06:00 at 18°C, 06:00-22:00 at 21°C, 22:00-24:00 at 18°C
        weekday_blocks = [
            ScheduleBlock(start_time=time(0, 0), temperature=18.0),
            ScheduleBlock(start_time=time(6, 0), temperature=21.0),
            ScheduleBlock(start_time=time(22, 0), temperature=18.0),
        ]

        # Default weekend schedule: 00:00-08:00 at 18°C, 08:00-23:00 at 21°C, 23:00-24:00 at 18°C
        weekend_blocks = [
            ScheduleBlock(start_time=time(0, 0), temperature=18.0),
            ScheduleBlock(start_time=time(8, 0), temperature=21.0),
            ScheduleBlock(start_time=time(23, 0), temperature=18.0),
        ]

        # Default homeoffice schedule: 00:00-06:00 at 18°C, 06:00-22:00 at 21°C, 22:00-24:00 at 18°C
        homeoffice_blocks = [
            ScheduleBlock(start_time=time(0, 0), temperature=18.0),
            ScheduleBlock(start_time=time(6, 0), temperature=21.0),
            ScheduleBlock(start_time=time(22, 0), temperature=18.0),
        ]

        room_schedule = RoomSchedule(
            room_name=self.room_config.name,
            normal_weekday=DaySchedule(
                schedule_type=SCHEDULE_TYPE_WEEKDAY, blocks=weekday_blocks
            ),
            normal_weekend=DaySchedule(
                schedule_type=SCHEDULE_TYPE_WEEKEND, blocks=weekend_blocks
            ),
            homeoffice_daily=DaySchedule(
                schedule_type=SCHEDULE_TYPE_DAILY, blocks=homeoffice_blocks
            ),
        )

        self.schedule_engine.update_room_schedule(self.room_config.name, room_schedule)

        # Save the default schedule
        await self.async_save_schedules()
        _LOGGER.info(
            "Created default schedule for room: %s (weekday, weekend, homeoffice)",
            self.room_config.name,
        )

    async def async_load_calibrations(self) -> None:
        """Load TRV calibrations from storage."""
        data = await self.calibration_store.async_load()
        if not data:
            _LOGGER.info(
                "No calibration data found for room: %s (using defaults)",
                self.room_config.name,
            )
            return

        try:
            from .core.calibration import CalibrationManager

            self.calibration_manager = CalibrationManager.from_dict(data)
            _LOGGER.debug("Loaded calibrations for room: %s", self.room_config.name)
        except (ValueError, KeyError) as err:
            _LOGGER.warning(
                "Failed to load calibrations for %s: %s", self.room_config.name, err
            )

    async def async_save_calibrations(self) -> None:
        """Save TRV calibrations to storage."""
        try:
            data = self.calibration_manager.to_dict()
            await self.calibration_store.async_save(data)
            _LOGGER.debug("Saved calibrations for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save calibrations for %s: %s", self.room_config.name, err
            )

    async def async_load_overshoot(self) -> None:
        """Load overshoot learning data from storage."""
        data = await self.overshoot_store.async_load()
        if not data:
            _LOGGER.info(
                "No overshoot data found for room: %s (using defaults)",
                self.room_config.name,
            )
            return

        try:
            self.overshoot_manager.load_from_dict(data)
            _LOGGER.debug("Loaded overshoot data for room: %s", self.room_config.name)
        except (ValueError, KeyError) as err:
            _LOGGER.warning(
                "Failed to load overshoot data for %s: %s", self.room_config.name, err
            )

    async def async_save_overshoot(self) -> None:
        """Save overshoot learning data to storage."""
        try:
            data = self.overshoot_manager.to_dict()
            await self.overshoot_store.async_save(data)
            _LOGGER.debug("Saved overshoot data for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save overshoot data for %s: %s", self.room_config.name, err
            )

    async def async_load_overrides(self) -> None:
        """Load override data from storage."""
        data = await self.override_store.async_load()
        if not data:
            _LOGGER.info("No override data found for room: %s", self.room_config.name)
            return

        try:
            self.override_manager = OverrideManager.from_dict(data)
            # Clear any expired overrides from storage
            self.override_manager.check_expired_overrides()
            _LOGGER.debug("Loaded overrides for room: %s", self.room_config.name)
        except (ValueError, KeyError) as err:
            _LOGGER.warning(
                "Failed to load overrides for %s: %s", self.room_config.name, err
            )

    async def async_save_overrides(self) -> None:
        """Save override data to storage."""
        try:
            data = self.override_manager.to_dict()
            await self.override_store.async_save(data)
            _LOGGER.debug("Saved overrides for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save overrides for %s: %s", self.room_config.name, err
            )

    async def async_load_thermal_mass(self) -> None:
        """Load thermal mass model from storage."""
        data = await self.thermal_mass_store.async_load()
        if not data:
            _LOGGER.info(
                "No thermal mass data found for room: %s (using defaults)",
                self.room_config.name,
            )
            return

        try:
            from .core.thermal_mass import ThermalMassModel

            self._thermal_mass_model = ThermalMassModel.from_dict(data)
            _LOGGER.info(
                "Loaded thermal mass for room %s: cooling_rate=%.2f°C/h, confidence=%.0f%%",
                self.room_config.name,
                self._thermal_mass_model.cooling_rate,
                self._thermal_mass_model.confidence * 100,
            )
        except (ValueError, KeyError) as err:
            _LOGGER.warning(
                "Failed to load thermal mass for %s: %s", self.room_config.name, err
            )

    async def async_save_thermal_mass(self) -> None:
        """Save thermal mass model to storage."""
        try:
            data = self._thermal_mass_model.to_dict()
            await self.thermal_mass_store.async_save(data)
            _LOGGER.debug("Saved thermal mass for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save thermal mass for %s: %s", self.room_config.name, err
            )

    async def async_load_feature_settings(self) -> None:
        """Load feature settings from storage."""
        data = await self.feature_store.async_load()

        if data is None:
            # First run: Use defaults from room config
            _LOGGER.info(
                "No feature settings found for room %s, using config defaults",
                self.room_config.name,
            )
            # Hysteresis is already loaded from room_data in __init__
            return

        # Load hysteresis from storage
        if "hysteresis" in data:
            hysteresis = data["hysteresis"]
            self.heating_controller.set_hysteresis(hysteresis)
            _LOGGER.debug(
                "Loaded hysteresis %.2f°C for room %s",
                hysteresis,
                self.room_config.name,
            )

        # Load PID settings from storage
        if "use_pid_control" in data:
            use_pid = data["use_pid_control"]
            if use_pid and not isinstance(
                self.heating_controller, PIDHeatingController
            ):
                # Switch to PID controller
                pid_config = PIDConfig(
                    kp=data.get("pid_kp", DEFAULT_PID_KP),
                    ki=data.get("pid_ki", DEFAULT_PID_KI),
                    kd=data.get("pid_kd", DEFAULT_PID_KD),
                )
                self.heating_controller = PIDHeatingController(pid_config)
                _LOGGER.info(
                    "Switched to PID controller for room %s (Kp=%.2f, Ki=%.3f, Kd=%.2f)",
                    self.room_config.name,
                    pid_config.kp,
                    pid_config.ki,
                    pid_config.kd,
                )
            elif not use_pid and isinstance(
                self.heating_controller, PIDHeatingController
            ):
                # Switch to basic controller
                hysteresis = self.heating_controller.hysteresis
                self.heating_controller = HeatingController(hysteresis=hysteresis)
                _LOGGER.info(
                    "Switched to basic controller for room %s", self.room_config.name
                )
            elif use_pid and isinstance(self.heating_controller, PIDHeatingController):
                # Update PID parameters
                self.heating_controller.config.kp = data.get("pid_kp", DEFAULT_PID_KP)
                self.heating_controller.config.ki = data.get("pid_ki", DEFAULT_PID_KI)
                self.heating_controller.config.kd = data.get("pid_kd", DEFAULT_PID_KD)
                _LOGGER.debug(
                    "Updated PID parameters for room %s (Kp=%.2f, Ki=%.3f, Kd=%.2f)",
                    self.room_config.name,
                    self.heating_controller.config.kp,
                    self.heating_controller.config.ki,
                    self.heating_controller.config.kd,
                )

        # Load heating curve settings from storage
        if "use_heating_curve" in data:
            use_curve = data["use_heating_curve"]
            if use_curve and self.heating_curve is None:
                # Enable heating curve
                curve_config = HeatingCurveConfig(
                    curve_slope=data.get(
                        "heating_curve_slope", DEFAULT_HEATING_CURVE_SLOPE
                    ),
                )
                self.heating_curve = HeatingCurve(curve_config)
                _LOGGER.info(
                    "Enabled heating curve for room %s (slope=%.2f)",
                    self.room_config.name,
                    curve_config.curve_slope,
                )
            elif not use_curve and self.heating_curve is not None:
                # Disable heating curve
                self.heating_curve = None
                _LOGGER.info(
                    "Disabled heating curve for room %s", self.room_config.name
                )
            elif use_curve and self.heating_curve is not None:
                # Update heating curve slope
                self.heating_curve.config.curve_slope = data.get(
                    "heating_curve_slope", DEFAULT_HEATING_CURVE_SLOPE
                )
                _LOGGER.debug(
                    "Updated heating curve slope for room %s (slope=%.2f)",
                    self.room_config.name,
                    self.heating_curve.config.curve_slope,
                )

        _LOGGER.info(
            "Loaded feature settings from storage for room %s", self.room_config.name
        )

    async def async_save_feature_settings(self) -> None:
        """Save feature settings to storage."""
        try:
            data = {
                "hysteresis": self.heating_controller.hysteresis,
                "use_pid_control": isinstance(
                    self.heating_controller, PIDHeatingController
                ),
            }

            # Save PID parameters if using PID controller
            if isinstance(self.heating_controller, PIDHeatingController):
                data["pid_kp"] = self.heating_controller.config.kp
                data["pid_ki"] = self.heating_controller.config.ki
                data["pid_kd"] = self.heating_controller.config.kd

            # Save heating curve settings
            data["use_heating_curve"] = self.heating_curve is not None
            if self.heating_curve is not None:
                data["heating_curve_slope"] = self.heating_curve.config.curve_slope

            await self.feature_store.async_save(data)
            _LOGGER.debug("Saved feature settings for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save feature settings for %s: %s",
                self.room_config.name,
                err,
            )

    async def async_save_schedules(self) -> None:
        """Save room schedules to storage."""
        try:
            if self.room_config.name in self.schedule_engine._room_schedules:
                room_schedule = self.schedule_engine._room_schedules[
                    self.room_config.name
                ]
                await self.schedule_store.async_save(room_schedule.to_dict())
                _LOGGER.debug("Saved schedule for room: %s", self.room_config.name)
        except Exception as err:
            _LOGGER.error(
                "Failed to save schedule for %s: %s", self.room_config.name, err
            )

    def get_hub_settings(self) -> dict[str, Any]:
        """Get hub global settings."""
        if self.hub_coordinator:
            return self.hub_coordinator.global_settings
        return {}

    def get_hub_mode(self) -> str:
        """Get current hub mode."""
        if self.hub_coordinator:
            # IMPORTANT: Call get_hub_mode() to trigger _update_hub_mode()
            # which reads the current state from the Select entity
            return self.hub_coordinator.get_hub_mode()
        return "normal"

    def get_early_start_offset(self) -> int:
        """
        Get effective early start offset (Room > Hub priority).

        Returns:
            Early start offset in minutes
        """
        # Room override has priority
        if self.room_config.early_start_offset is not None:
            return self.room_config.early_start_offset

        # Fallback to hub setting
        hub_settings = self.get_hub_settings()
        return hub_settings.get(
            CONF_GLOBAL_EARLY_START_OFFSET, DEFAULT_EARLY_START_OFFSET
        )

    def get_early_start_max(self) -> int:
        """
        Get effective early start maximum (Room > Hub priority).

        Returns:
            Early start maximum in minutes
        """
        # Room override has priority
        if self.room_config.early_start_max is not None:
            return self.room_config.early_start_max

        # Fallback to hub setting
        hub_settings = self.get_hub_settings()
        return hub_settings.get(CONF_GLOBAL_EARLY_START_MAX, DEFAULT_EARLY_START_MAX)

    def get_override_timeout(self) -> str:
        """
        Get effective override timeout mode (Room > Hub priority).

        Returns:
            Override timeout mode string
        """
        # Room override has priority
        if self.room_config.override_timeout is not None:
            return self.room_config.override_timeout

        # Fallback to hub setting
        hub_settings = self.get_hub_settings()
        return hub_settings.get(
            CONF_GLOBAL_OVERRIDE_TIMEOUT, DEFAULT_GLOBAL_OVERRIDE_TIMEOUT
        )

    def get_current_temperature(self) -> float | None:
        """Get current room temperature (fused from all sensors)."""
        if hasattr(self, 'current_room_data') and self.current_room_data:
            return self.current_room_data.current_temperature
        return getattr(self, '_last_fused_temp', None)

    def get_scheduled_target(self) -> float | None:
        """Get scheduled target temperature for this room (with optional heating curve and weather prediction)."""
        mode = self.get_hub_mode()

        base_target = self.schedule_engine.get_target_temperature(
            self.room_config.name, mode
        )

        self.debug("rooms", "get_scheduled_target - mode=%s, target=%s", mode, base_target)

        # Apply heating curve if enabled and outdoor temp available
        if (
            base_target is not None
            and self.heating_curve is not None
            and self._cached_outdoor_temp is not None
        ):
            adjusted_target = self.heating_curve.calculate_target(
                self._cached_outdoor_temp, base_target
            )
            _LOGGER.debug(
                "Room %s: Heating curve applied: base=%.1f°C, outdoor=%.1f°C, adjusted=%.1f°C",
                self.room_config.name,
                base_target,
                self._cached_outdoor_temp,
                adjusted_target,
            )
            base_target = adjusted_target

        # Apply weather prediction adjustment if enabled (Phase 3.3)
        if (
            base_target is not None
            and self.room_config.use_weather_prediction
            and self.hub_coordinator
            and self._cached_outdoor_temp is not None
        ):
            weather_adjustment = self.hub_coordinator.get_weather_adjustment(
                self._cached_outdoor_temp
            )
            if abs(weather_adjustment) > 0.1:  # Only apply meaningful adjustments
                adjusted = base_target + weather_adjustment
                _LOGGER.debug(
                    "Room %s: Weather prediction applied: base=%.1f°C, adj=%.1f°C, result=%.1f°C",
                    self.room_config.name,
                    base_target,
                    weather_adjustment,
                    adjusted,
                )
                base_target = adjusted

        # Apply room coupling adjustment if enabled (Phase 3.2)
        if (
            base_target is not None
            and self.room_config.use_room_coupling
            and self.hub_coordinator
            and self.room_config.adjacent_rooms
        ):
            coupling_adjustment = (
                self.hub_coordinator.room_coupling_manager.get_coupling_adjustment(
                    self.room_config.name
                )
            )
            if abs(coupling_adjustment) > 0.05:  # Only apply meaningful adjustments
                adjusted = base_target + coupling_adjustment
                _LOGGER.debug(
                    "Room %s: Room coupling applied: base=%.1f°C, adj=%.1f°C, result=%.1f°C",
                    self.room_config.name,
                    base_target,
                    coupling_adjustment,
                    adjusted,
                )
                base_target = adjusted

        # Apply overshoot compensation if learned (helps On/Off TRVs and old radiators)
        if base_target is not None and hasattr(self, 'overshoot_manager'):
            current_temp = self.get_current_temperature()
            outdoor_temp = self._cached_outdoor_temp
            
            # Update overshoot tracking with current temperature
            self.overshoot_manager.update_temperature(
                self.room_config.name, current_temp, outdoor_temp
            )
            
            # Get compensated target
            compensated = self.overshoot_manager.get_compensated_target(
                self.room_config.name, base_target
            )
            if abs(compensated - base_target) > 0.05:
                _LOGGER.debug(
                    "Room %s: Overshoot compensation applied: base=%.1f°C, compensated=%.1f°C",
                    self.room_config.name, base_target, compensated
                )
                base_target = compensated

        return base_target

    def setup_state_listeners(self) -> None:
        """Set up state listeners for TRV entities to detect manual overrides."""
        # Remove any existing listeners
        for remove_listener in self._state_listeners:
            remove_listener()
        self._state_listeners.clear()

        # Set up listener for each TRV
        for trv_id in self.room_config.trv_entity_ids:
            remove_listener = async_track_state_change_event(
                self.hass,
                [trv_id],
                self._handle_trv_state_change,
            )
            self._state_listeners.append(remove_listener)
            _LOGGER.debug("Set up state listener for TRV: %s", trv_id)

    @callback
    def _handle_trv_state_change(self, event: Event) -> None:
        """Handle TRV state change to detect manual overrides."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state or not old_state:
            return

        # Context-based echo detection
        # If this event was caused by our own command, ignore it
        if self.trv_manager.is_own_context(event.context):
            _LOGGER.debug(
                "TRV %s: Ignoring echo of our own command (context match)",
                entity_id
            )
            return

        # Get temperature attribute
        new_temp_attr = new_state.attributes.get("temperature")
        old_temp_attr = old_state.attributes.get("temperature")

        if new_temp_attr is None or old_temp_attr is None:
            return


        try:
            new_temp = float(new_temp_attr)
            old_temp = float(old_temp_attr)
        except (ValueError, TypeError):
            return

        # Check if temperature actually changed
        if abs(new_temp - old_temp) < 0.1:
            return

        # Get hub mode to determine reference value and timeout
        hub_mode = self.get_hub_mode()
        
        # Determine reference value based on mode
        if hub_mode == "off":
            # Off mode: reference is frost protection
            reference_target = self.hub_coordinator.get_frost_protection_temp() if self.hub_coordinator else 5.0
            override_timeout = "2h"  # 2 hour temporary override in off mode
        elif hub_mode == "manual":
            # Manual mode: reference is last commanded target
            reference_target = self._commanded_target
            override_timeout = OVERRIDE_TIMEOUT_NEVER  # Never expires in manual mode
        else:
            # Schedule mode: reference is scheduled target
            reference_target = self.get_scheduled_target()
            override_timeout = self.get_override_timeout()
        
        # If no reference value available, cannot create override
        if reference_target is None:
            _LOGGER.debug(
                "TRV %s: No reference temperature available for override detection",
                entity_id
            )
            return

        # If timeout mode is "always", reject manual overrides (only in schedule mode)
        if hub_mode not in ("manual", "off") and override_timeout == OVERRIDE_TIMEOUT_ALWAYS:
            _LOGGER.info(
                "Manual override detected for %s but timeout mode is 'always', "
                "will restore scheduled temperature",
                entity_id,
            )
            # Schedule restoration in next update cycle
            return

        # Check if this is a manual override (different from reference)
        if abs(new_temp - reference_target) > 0.2:
            # Store last known target to detect TaDIY vs manual changes
            last_known = self._last_trv_targets.get(entity_id)

            # Only create override if this wasn't set by TaDIY
            if last_known is None or abs(new_temp - last_known) > 0.2:
                # Get next schedule block time for timeout calculation (only relevant for schedule mode)
                next_block_time = None
                if hub_mode not in ("manual", "off"):
                    next_change = self.schedule_engine.get_next_schedule_change(
                        self.room_config.name, hub_mode
                    )
                    next_block_time = next_change[0] if next_change else None

                # Create override record
                _LOGGER.info(
                    "TRV %s: Creating override in %s mode (reference=%.1f, override=%.1f, timeout=%s)",
                    entity_id, hub_mode, reference_target, new_temp, override_timeout
                )
                self.override_manager.create_override(
                    entity_id=entity_id,
                    scheduled_temp=reference_target,
                    override_temp=new_temp,
                    timeout_mode=override_timeout,
                    next_block_time=next_block_time,
                )

                # Save overrides to storage
                self.hass.async_create_task(self.async_save_overrides())

        # Update last known target
        self._last_trv_targets[entity_id] = new_temp


    def check_window_override(self, current_target: float) -> bool:
        """Check if window open overrides heating."""
        if (
            self.current_room_data
            and self.current_room_data.window_state.heating_should_stop
        ):
            return True
        return False

    async def _async_update_data(self) -> RoomData:
        """Fetch and process room data using modular managers."""
        self.debug("rooms", "Starting room update cycle")

        # 1. Gather Sensor Data
        fused_temp = self.sensor_manager.get_fused_temperature()
        outdoor_temp = self.sensor_manager.get_outdoor_temperature()
        window_open = self.sensor_manager.is_window_open()
        humidity = self.sensor_manager.get_humidity()

        # 2. Get Hub and TRV states
        hub_mode = self.get_hub_mode()
        trv_state = self.trv_manager.get_current_trv_state()
        
        # 3. Handle Window Logic
        window_state = self._calculate_window_state(window_open)
        
        # 4. Determine Target Temperature
        scheduled_target = self.get_scheduled_target()
        
        # Check for expired overrides first
        expired = self.override_manager.check_expired_overrides()
        if expired:
            _LOGGER.warning("Room %s: Expired overrides cleared: %s", self.room_config.name, expired)
        
        active_override = self.override_manager.get_active_override()
        override_target = active_override.override_temp if active_override else None
        
        _LOGGER.warning(
            "Room %s: UPDATE CYCLE - hub_mode=%s, scheduled=%.1f, override=%s, commanded=%.1f, window=%s, open=%s",
            self.room_config.name,
            hub_mode,
            scheduled_target or 0,
            active_override,
            self._commanded_target or 0,
            window_state.is_open,
            window_open
        )
        
        final_target, enforce_target = self.orchestrator.calculate_target_temperature(
            scheduled_target=scheduled_target,
            active_override_target=override_target,
            hub_mode=hub_mode,
            outdoor_temp=outdoor_temp,
            window_should_stop=window_state.heating_should_stop
        )

        _LOGGER.warning(
            "Room %s: RESULT - final_target=%s, enforce=%s",
            self.room_config.name,
            final_target,
            enforce_target
        )

        # 5. Inhibit selection bounce (Grace Period)
        # If we are in grace period, we ignore the TRV's reported target and stick to what we sent
        if self.orchestrator.is_in_grace_period():
            self.debug("rooms", "Grace Period Active: Prioritizing target %.1f over TRV %.1f", 
                       final_target, trv_state["target"])
        else:
            # If TRV target changed significantly and we AREN'T enforcing a schedule, 
            # we should detect this as a manual change (echo detection)
            # This is partly handled by setup_state_listeners, but we sync here too.
            pass

        # 6. Apply Target if needed and store commanded target
        if enforce_target and final_target is not None:
            # Determine if we should heat based on temperature demand
            # Pass "heat" as intended mode since we ARE enforcing a target
            # (the decision should be based on temp difference, not current TRV state)
            should_heat = self.orchestrator.calculate_heating_decision(
                fused_temp=fused_temp,
                target_temp=final_target,
                hvac_mode="heat"  # We intend to heat when enforcing a target
            )
            
            _LOGGER.warning(
                "Room %s: Heating decision - fused=%.1f, target=%.1f, should_heat=%s",
                self.room_config.name,
                fused_temp or 0,
                final_target,
                should_heat
            )
            
            await self.trv_manager.apply_target(final_target, should_heat=should_heat)
            
            # Track overshoot learning - start cycle when heating begins
            if hasattr(self, 'overshoot_manager') and should_heat and fused_temp is not None:
                self.overshoot_manager.start_heating_cycle(
                    self.room_config.name, fused_temp, final_target
                )
            elif hasattr(self, 'overshoot_manager') and not should_heat:
                self.overshoot_manager.end_heating_cycle(self.room_config.name)
            
            # Command and Remember: Store what we just commanded
            self._commanded_target = final_target
            self._commanded_hvac_mode = "heat" if should_heat else "off"
            
            # Heating is active based on our decision, not TRV state
            heating_active = should_heat
        else:
            # Manual mode or no enforcement - use TRV's current target
            self._commanded_target = trv_state["target"]
            heating_active = trv_state["mode"] == "heat"

        # 7. Update models (Learning)
        if fused_temp is not None:
             # Heat-up Model Tracking (Learning heating rate)
             if heating_active:
                 prev_temp = getattr(self, "_last_fused_temp", None)
                 prev_time = getattr(self, "_last_temp_time", None)
                 now = dt_util.utcnow()
                 
                 if prev_temp is not None and prev_time is not None:
                     time_delta = (now - prev_time).total_seconds() / 60.0
                     if time_delta >= 5.0:
                         temp_increase = fused_temp - prev_temp
                         if temp_increase > 0.01:
                             try:
                                 self._heat_model.update_with_measurement(temp_increase, time_delta)
                             except ValueError:
                                 pass
                             self._last_temp_time = now
                 
                 if not getattr(self, "_last_temp_time", None):
                     self._last_temp_time = now
             
             # Thermal Mass Model Tracking (Learning cooling rate)
             self._thermal_mass_model.start_cooling_measurement(fused_temp, heating_active)
             if not heating_active:
                 if self._thermal_mass_model.update_with_cooling_measurement(fused_temp, outdoor_temp):
                     self.hass.async_create_task(self.async_save_thermal_mass())
             
             self._last_fused_temp = fused_temp

        # 8. Create RoomData using COMMANDED target (not TRV feedback)
        room_data = RoomData(
            room_name=self.room_config.name,
            current_temperature=fused_temp if fused_temp is not None else 20.0,
            main_sensor_temperature=self.sensor_manager._get_sensor_value(self.room_config.main_temp_sensor_id) or 0.0,
            trv_temperatures=trv_state["all_targets"],
            window_state=window_state,
            outdoor_temperature=outdoor_temp,
            target_temperature=self._commanded_target,  # Use commanded target!
            hvac_mode=self._commanded_hvac_mode if enforce_target else trv_state["mode"],
            humidity=humidity,
            heating_active=heating_active,
            heating_rate=self._heat_model.get_heating_rate(),
            heating_rate_sample_count=self._heat_model.sample_count,
            heating_rate_confidence=self._heat_model.get_confidence(),
            override_active=active_override is not None,
            override_count=1 if active_override else 0
        )
        
        # Increment update counter
        self._update_count += 1
        
        self.current_room_data = room_data
        return room_data

    def _calculate_window_state(self, window_open: bool) -> WindowState:
        """Calculate current window state."""
        if not window_open:
            return WindowState(
                is_open=False,
                heating_should_stop=False,
                reason="window_closed",
            )

        return WindowState(
            is_open=True,
            heating_should_stop=True,
            reason="window_open_heating_disabled",
            timeout_active=True,
            last_change=dt_util.utcnow(),
        )

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and cleanup."""
        # Unregister from room coupling manager
        if self.hub_coordinator and self.room_config.use_room_coupling:
            self.hub_coordinator.room_coupling_manager.unregister_room(
                self.room_config.name
            )
            _LOGGER.debug(
                "Unregistered room %s from coupling manager", self.room_config.name
            )

        # Remove state listeners
        for remove_listener in self._state_listeners:
            remove_listener()
        self._state_listeners.clear()
