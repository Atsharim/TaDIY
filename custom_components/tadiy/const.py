"""Constants for the TaDIY integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

DOMAIN: Final = "tadiy"


# Version from manifest.json
def _get_version() -> str:
    """Get version from manifest.json."""
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
            return manifest.get("version", "unknown")
    except Exception:
        return "unknown"


VERSION: Final = _get_version()

# Configuration
CONF_HUB: Final = "is_hub"
CONF_ROOM_NAME: Final = "room_name"
CONF_TRV_ENTITIES: Final = "trv_entities"
CONF_MAIN_TEMP_SENSOR: Final = "main_temp_sensor"
CONF_WINDOW_SENSORS: Final = "window_sensors"
CONF_OUTDOOR_SENSOR: Final = "outdoor_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"  # Optional humidity sensor for room
CONF_WEATHER_ENTITY: Final = "weather_entity"  # Optional weather entity for hub (fallback outdoor temp + forecast)
CONF_PERSON_ENTITIES: Final = (
    "person_entities"  # Optional person entities for location-based control
)
CONF_LOCATION_MODE_ENABLED: Final = (
    "location_mode_enabled"  # Enable location-based control
)
CONF_CUSTOM_MODES: Final = "custom_modes"  # Additional custom modes for hub
CONF_SHOW_PANEL: Final = "show_panel"  # Show schedules panel in sidebar

# Global defaults (Hub-level)
CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: Final = "global_window_open_timeout"
CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: Final = "global_window_close_timeout"
CONF_GLOBAL_DONT_HEAT_BELOW: Final = "global_dont_heat_below"
CONF_GLOBAL_USE_EARLY_START: Final = "global_use_early_start"
CONF_GLOBAL_LEARN_HEATING_RATE: Final = "global_learn_heating_rate"
CONF_GLOBAL_EARLY_START_OFFSET: Final = "global_early_start_offset"
CONF_GLOBAL_EARLY_START_MAX: Final = "global_early_start_max"

# Room-specific overrides
CONF_WINDOW_OPEN_TIMEOUT: Final = "window_open_timeout"
CONF_WINDOW_CLOSE_TIMEOUT: Final = "window_close_timeout"
CONF_DONT_HEAT_BELOW: Final = "dont_heat_below_outdoor"
CONF_USE_EARLY_START: Final = "use_early_start"
CONF_LEARN_HEATING_RATE: Final = "learn_heating_rate"
CONF_TARGET_TEMP_STEP: Final = "target_temp_step"
CONF_TOLERANCE: Final = "tolerance"
CONF_EARLY_START_OFFSET: Final = "early_start_offset"
CONF_EARLY_START_MAX: Final = "early_start_max"
CONF_MIN_HEATING_RATE: Final = "min_heating_rate"
CONF_MAX_HEATING_RATE: Final = "max_heating_rate"
CONF_FROST_PROTECTION_TEMP: Final = "frost_protection_temp"

# Override timeout settings (Hub + Room level)
CONF_GLOBAL_OVERRIDE_TIMEOUT: Final = "global_override_timeout"
CONF_OVERRIDE_TIMEOUT: Final = "override_timeout"

# Override timeout options (Hub: never, 1h, 2h, 3h, 4h, next_block, next_day)
# Room adds "always" option
OVERRIDE_TIMEOUT_NEVER: Final = "never"
OVERRIDE_TIMEOUT_1H: Final = "1h"
OVERRIDE_TIMEOUT_2H: Final = "2h"
OVERRIDE_TIMEOUT_3H: Final = "3h"
OVERRIDE_TIMEOUT_4H: Final = "4h"
OVERRIDE_TIMEOUT_NEXT_BLOCK: Final = "next_block"
OVERRIDE_TIMEOUT_NEXT_DAY: Final = "next_day"
OVERRIDE_TIMEOUT_ALWAYS: Final = "always"  # Room only

DEFAULT_GLOBAL_OVERRIDE_TIMEOUT: Final = OVERRIDE_TIMEOUT_NEXT_BLOCK
DEFAULT_OVERRIDE_TIMEOUT: Final = None  # None = use hub setting

# Override timeout durations in minutes
OVERRIDE_TIMEOUT_DURATIONS: Final = {
    OVERRIDE_TIMEOUT_1H: 60,
    OVERRIDE_TIMEOUT_2H: 120,
    OVERRIDE_TIMEOUT_3H: 180,
    OVERRIDE_TIMEOUT_4H: 240,
}

# Schedule configuration
CONF_SCHEDULES: Final = "schedules"
CONF_SCHEDULE_NAME: Final = "schedule_name"
CONF_SCHEDULE_ENTRIES: Final = "schedule_entries"
CONF_SCHEDULE_TIME: Final = "time"
CONF_SCHEDULE_TEMP: Final = "temperature"

# Default values
DEFAULT_NAME: Final = "TaDIY Hub"
DEFAULT_WINDOW_OPEN_TIMEOUT: Final = 300  # 5 minutes
DEFAULT_WINDOW_CLOSE_TIMEOUT: Final = 180  # 3 minutes
DEFAULT_DONT_HEAT_BELOW: Final = (
    0.0  # 0 = disabled (don't heat when outdoor temp >= this)
)
DEFAULT_USE_EARLY_START: Final = True
DEFAULT_LEARN_HEATING_RATE: Final = True
DEFAULT_TARGET_TEMP_STEP: Final = 0.5
DEFAULT_TOLERANCE: Final = 0.3
DEFAULT_EARLY_START_OFFSET: Final = 5  # minutes
DEFAULT_EARLY_START_MAX: Final = 120  # 2 hours max pre-heat
DEFAULT_MIN_HEATING_RATE: Final = 0.5  # °C/h - für Options Flow
DEFAULT_MAX_HEATING_RATE: Final = 3.0  # °C/h - für Options Flow
DEFAULT_HEATING_RATE: Final = 1.0
DEFAULT_FROST_PROTECTION_TEMP: Final = 12.0  # DEBUG: Raised to identify if this is the source

# Heating rate limits (validation boundaries)
MIN_HEATING_RATE: Final = 0.05  # Absolute minimum (°C/h)
MAX_HEATING_RATE: Final = 10.0  # Absolute maximum (°C/h)

# Hysteresis settings (anti-cycling deadband)
DEFAULT_HYSTERESIS: Final = 0.3  # °C deadband to prevent rapid cycling
MIN_HYSTERESIS: Final = 0.1  # Minimum hysteresis
MAX_HYSTERESIS: Final = 2.0  # Maximum hysteresis

# TRV Calibration (automatic by default as per user preference)
CONF_TRV_CALIBRATION_MODE: Final = "trv_calibration_mode"
DEFAULT_TRV_CALIBRATION_MODE: Final = "auto"  # auto | manual | disabled
DEFAULT_TRV_MULTIPLIER: Final = 1.0
MIN_TRV_MULTIPLIER: Final = 0.5
MAX_TRV_MULTIPLIER: Final = 2.0
DEFAULT_TRV_OFFSET: Final = 0.0  # Only used in manual mode
MIN_TRV_OFFSET: Final = -10.0
MAX_TRV_OFFSET: Final = 10.0

# Hysteresis settings
CONF_HYSTERESIS: Final = "hysteresis"
DEFAULT_HYSTERESIS: Final = 0.3  # °C deadband
MIN_HYSTERESIS: Final = 0.1
MAX_HYSTERESIS: Final = 2.0

# PID Control settings
CONF_USE_PID_CONTROL: Final = "use_pid_control"
DEFAULT_USE_PID_CONTROL: Final = False  # Disabled by default, opt-in available
CONF_PID_KP: Final = "pid_kp"
CONF_PID_KI: Final = "pid_ki"
CONF_PID_KD: Final = "pid_kd"
DEFAULT_PID_KP: Final = 0.5
DEFAULT_PID_KI: Final = 0.01
DEFAULT_PID_KD: Final = 0.1

# Heating Curve settings
CONF_USE_HEATING_CURVE: Final = "use_heating_curve"
DEFAULT_USE_HEATING_CURVE: Final = False  # Disabled by default, opt-in available
CONF_HEATING_CURVE_SLOPE: Final = "heating_curve_slope"
DEFAULT_HEATING_CURVE_SLOPE: Final = 0.5
MIN_HEATING_CURVE_SLOPE: Final = 0.1

# TRV HVAC Mode Control (for Moes and similar TRVs)
CONF_USE_HVAC_OFF_FOR_LOW_TEMP: Final = "use_hvac_off_for_low_temp"
DEFAULT_USE_HVAC_OFF_FOR_LOW_TEMP: Final = (
    False  # Disabled by default, opt-in for Moes TRVs
)

# Weather Prediction (Phase 3.3)
CONF_USE_WEATHER_PREDICTION: Final = "use_weather_prediction"
DEFAULT_USE_WEATHER_PREDICTION: Final = False  # Disabled by default, opt-in

# Multi-Room Heat Coupling (Phase 3.2)
CONF_ADJACENT_ROOMS: Final = "adjacent_rooms"
CONF_USE_ROOM_COUPLING: Final = "use_room_coupling"
DEFAULT_USE_ROOM_COUPLING: Final = False  # Disabled by default, opt-in
CONF_COUPLING_STRENGTH: Final = "coupling_strength"
DEFAULT_COUPLING_STRENGTH: Final = 0.5  # Temperature adjustment factor (0.0-1.0)

# Thermal Mass Learning settings
CONF_LEARN_COOLING_RATE: Final = "learn_cooling_rate"
DEFAULT_LEARN_COOLING_RATE: Final = True  # Enabled by default, opt-out available
DEFAULT_COOLING_RATE: Final = 0.5  # °C/h conservative default
MIN_COOLING_RATE: Final = 0.1
MAX_COOLING_RATE: Final = 3.0
MAX_HEATING_CURVE_SLOPE: Final = 2.0

# Frost Protection limits
MIN_FROST_PROTECTION: Final = -5.0  # Minimum frost protection temperature
MAX_FROST_PROTECTION: Final = 15.0  # Maximum frost protection temperature

# Window timeout validation
MIN_WINDOW_TIMEOUT: Final = 10  # seconds
MAX_WINDOW_TIMEOUT: Final = 3600  # seconds (1 hour)

# Boost limits
MIN_BOOST_TEMP: Final = 15.0
MAX_BOOST_TEMP: Final = 35.0
MIN_BOOST_DURATION: Final = 5  # minutes
MAX_BOOST_DURATION: Final = 240  # minutes

# Device info
MANUFACTURER: Final = "TaDIY"
MODEL_NAME: Final = "Adaptive Climate Orchestrator"
MODEL_ROOM: Final = "Room Controller"

# Icons
ICON_FROST: Final = "mdi:snowflake"
ICON_BOOST: Final = "mdi:rocket-launch"
ICON_MODE: Final = "mdi:home-automation"
ICON_TEMPERATURE: Final = "mdi:thermometer"
ICON_WINDOW: Final = "mdi:window-open-variant"
ICON_LEARNING: Final = "mdi:brain"

# Services
SERVICE_FORCE_REFRESH: Final = "force_refresh"
SERVICE_RESET_LEARNING: Final = "reset_learning"
SERVICE_SET_HUB_MODE: Final = "set_hub_mode"
SERVICE_BOOST_ALL_ROOMS: Final = "boost_all_rooms"
SERVICE_SET_HEATING_CURVE: Final = "set_heating_curve"
SERVICE_GET_SCHEDULE: Final = "get_schedule"
SERVICE_SET_SCHEDULE: Final = "set_schedule"
SERVICE_SET_TRV_CALIBRATION: Final = "set_trv_calibration"
SERVICE_CLEAR_OVERRIDE: Final = "clear_override"
SERVICE_SET_LOCATION_OVERRIDE: Final = "set_location_override"
SERVICE_START_PID_AUTOTUNE: Final = "start_pid_autotune"
SERVICE_STOP_PID_AUTOTUNE: Final = "stop_pid_autotune"
SERVICE_APPLY_PID_AUTOTUNE: Final = "apply_pid_autotune"
SERVICE_REFRESH_WEATHER_FORECAST: Final = "refresh_weather_forecast"

# Service attributes
ATTR_ROOM: Final = "room"
ATTR_MODE: Final = "mode"
ATTR_TEMPERATURE: Final = "temperature"
ATTR_DURATION_MINUTES: Final = "duration_minutes"
ATTR_HEATING_RATE: Final = "heating_rate"
ATTR_ENTITY_ID: Final = "entity_id"
ATTR_SCHEDULE_TYPE: Final = "schedule_type"
ATTR_BLOCKS: Final = "blocks"
ATTR_OFFSET: Final = "offset"
ATTR_MULTIPLIER: Final = "multiplier"
ATTR_LOCATION_OVERRIDE: Final = "location_override"

# Hub modes
HUB_MODE_NORMAL: Final = "normal"
HUB_MODE_HOMEOFFICE: Final = "homeoffice"
MODE_MANUAL: Final = "manual"
MODE_OFF: Final = "off"

# Default modes (cannot be deleted)
DEFAULT_HUB_MODES: Final = [
    HUB_MODE_NORMAL,
    HUB_MODE_HOMEOFFICE,
    MODE_MANUAL,
    MODE_OFF,
]

# Mode limits
MAX_CUSTOM_MODES: Final = 10  # Maximum total number of modes (including defaults)

# Legacy mode names (kept for reference, user can create these if needed)
HUB_MODE_VACATION: Final = "vacation"
HUB_MODE_PARTY: Final = "party"

DEFAULT_HUB_MODE: Final = HUB_MODE_NORMAL

# Boost defaults
DEFAULT_BOOST_TEMPERATURE: Final = 24.0
DEFAULT_BOOST_DURATION: Final = 60

# Update intervals
UPDATE_INTERVAL: Final = 30
HUB_UPDATE_INTERVAL: Final = 60
ROOM_UPDATE_INTERVAL: Final = 30

# Storage keys
STORAGE_VERSION: Final = 1
STORAGE_VERSION_SCHEDULES: Final = 1
STORAGE_VERSION_LEARNING: Final = 1
STORAGE_KEY: Final = "tadiy"
STORAGE_KEY_LEARNING: Final = "learning_data"
STORAGE_KEY_SCHEDULES: Final = "schedules"
STORAGE_KEY_FEATURES: Final = "features"

# Window states
WINDOW_STATE_CLOSED: Final = "closed"
WINDOW_STATE_OPEN_GRACE: Final = "open_within_timeout"
WINDOW_STATE_OPEN_HEATING_STOPPED: Final = "open_heating_stopped"
WINDOW_STATE_CLOSED_COOLDOWN: Final = "closed_cooldown"

# Schedule types
SCHEDULE_NORMAL_WEEKDAY: Final = "normal_weekday"
SCHEDULE_NORMAL_WEEKEND: Final = "normal_weekend"
SCHEDULE_HOMEOFFICE: Final = "homeoffice"
SCHEDULE_VACATION: Final = "vacation"
SCHEDULE_PARTY: Final = "party"

# Schedule type constants (für models/schedule.py)
SCHEDULE_TYPE_DAILY: Final = "daily"
SCHEDULE_TYPE_WEEKDAY: Final = "weekday"
SCHEDULE_TYPE_WEEKEND: Final = "weekend"

# Schedule special temperatures
SCHEDULE_TEMP_FROST: Final = "frost"
SCHEDULE_TEMP_OFF: Final = "off"

DEFAULT_SCHEDULES: Final = {
    SCHEDULE_NORMAL_WEEKDAY: [
        {"time": "06:00", "temperature": 21.0},
        {"time": "08:00", "temperature": 18.0},
        {"time": "16:00", "temperature": 21.0},
        {"time": "22:00", "temperature": 18.0},
    ],
    SCHEDULE_NORMAL_WEEKEND: [
        {"time": "08:00", "temperature": 21.0},
        {"time": "23:00", "temperature": 18.0},
    ],
    SCHEDULE_HOMEOFFICE: [
        {"time": "06:00", "temperature": 21.0},
        {"time": "22:00", "temperature": 18.0},
    ],
    SCHEDULE_VACATION: [
        {"time": "00:00", "temperature": 16.0},
    ],
    SCHEDULE_PARTY: [
        {"time": "00:00", "temperature": 22.0},
    ],
}

# Temperature limits
MIN_TEMP: Final = 5.0
MAX_TEMP: Final = 30.0
DEFAULT_MIN_TEMP: Final = 5.0
DEFAULT_MAX_TEMP: Final = 30.0
MIN_TARGET_TEMP: Final = 5.0  # Verwendet in models
MAX_TARGET_TEMP: Final = 30.0  # Verwendet in models

# HVAC modes
HVAC_MODE_OFF: Final = "off"
HVAC_MODE_HEAT: Final = "heat"
HVAC_MODE_AUTO: Final = "auto"

# Preset modes
PRESET_NONE: Final = "none"
PRESET_AWAY: Final = "away"
PRESET_COMFORT: Final = "comfort"
PRESET_ECO: Final = "eco"
PRESET_BOOST: Final = "boost"
PRESET_FROST_PROTECTION: Final = "frost_protection"

# Entity name templates
ENTITY_NAME_CLIMATE: Final = "{room_name}"
ENTITY_NAME_TEMP_SENSOR: Final = "{room_name} Temperature"
ENTITY_NAME_WINDOW_SENSOR: Final = "{room_name} Window State"
ENTITY_NAME_HEATING_RATE: Final = "{room_name} Heating Rate"
