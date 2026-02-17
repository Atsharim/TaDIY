"""Constants for the TaDIY integration."""

from typing import Final

DOMAIN: Final = "tadiy"
MANUFACTURER: Final = "TaDIY"
MODEL_NAME: Final = "Adaptive Climate Orchestrator"

STORAGE_KEY: Final = f"{DOMAIN}_storage"
STORAGE_VERSION: Final = 1
STORAGE_KEY_SCHEDULES: Final = f"{DOMAIN}_schedules"
STORAGE_VERSION_SCHEDULES: Final = 1

# Hub Modes
MODE_NORMAL: Final = "normal"
MODE_HOMEOFFICE: Final = "homeoffice"
MODE_MANUAL: Final = "manual"
MODE_OFF: Final = "off"
HUB_MODES: Final = [MODE_NORMAL, MODE_HOMEOFFICE, MODE_MANUAL, MODE_OFF]

# Schedule Types
SCHEDULE_TYPE_WEEKDAY: Final = "weekday"
SCHEDULE_TYPE_WEEKEND: Final = "weekend"
SCHEDULE_TYPE_DAILY: Final = "daily"

# Schedule Block Temperature Special Values
SCHEDULE_TEMP_FROST: Final = "frost"
SCHEDULE_TEMP_OFF: Final = "off"

# Configuration Keys
CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: Final = "global_window_open_timeout"
CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: Final = "global_window_close_timeout"
CONF_GLOBAL_DONT_HEAT_BELOW: Final = "global_dont_heat_below_outdoor"
CONF_GLOBAL_USE_EARLY_START: Final = "global_use_early_start"
CONF_GLOBAL_LEARN_HEATING_RATE: Final = "global_learn_heating_rate"

CONF_HUB_MODE: Final = "hub_mode"
CONF_FROST_PROTECTION_TEMP: Final = "frost_protection_temp"
CONF_BOOST_TEMPERATURE: Final = "boost_temperature"
CONF_BOOST_DURATION: Final = "boost_duration_minutes"

CONF_ROOMS: Final = "rooms"
CONF_ROOM_NAME: Final = "room_name"
CONF_TRV_ENTITIES: Final = "trv_entities"
CONF_MAIN_TEMP_SENSOR: Final = "main_temp_sensor"
CONF_WINDOW_SENSORS: Final = "window_sensors"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_OUTDOOR_SENSOR: Final = "outdoor_sensor"
CONF_WINDOW_OPEN_TIMEOUT: Final = "window_open_timeout"
CONF_WINDOW_CLOSE_TIMEOUT: Final = "window_close_timeout"
CONF_DONT_HEAT_BELOW_OUTDOOR: Final = "dont_heat_below_outdoor"
CONF_TARGET_TEMP_STEP: Final = "target_temp_step"
CONF_TOLERANCE: Final = "tolerance"
CONF_USE_EARLY_START: Final = "use_early_start"
CONF_LEARN_HEATING_RATE: Final = "learn_heating_rate"
CONF_USE_HUMIDITY_COMPENSATION: Final = "use_humidity_compensation"
CONF_WINDOW_OPEN_DELAY: Final = CONF_WINDOW_OPEN_TIMEOUT
CONF_WINDOW_CLOSE_DELAY: Final = CONF_WINDOW_CLOSE_TIMEOUT

DEFAULT_NAME: Final = "TaDIY Hub"
DEFAULT_WINDOW_OPEN_TIMEOUT: Final = 30
DEFAULT_WINDOW_CLOSE_TIMEOUT: Final = 300
DEFAULT_DONT_HEAT_BELOW: Final = 20.0
DEFAULT_TOLERANCE: Final = "auto"
DEFAULT_TARGET_TEMP_STEP: Final = "auto"
DEFAULT_USE_EARLY_START: Final = True
DEFAULT_LEARN_HEATING_RATE: Final = True
DEFAULT_USE_HUMIDITY_COMPENSATION: Final = False

DEFAULT_HUB_MODE: Final = MODE_NORMAL
DEFAULT_FROST_PROTECTION_TEMP: Final = 15.0
DEFAULT_BOOST_TEMPERATURE: Final = 30.0
DEFAULT_BOOST_DURATION: Final = 60

TEMP_STEP_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]
TOLERANCE_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]

SERVICE_FORCE_REFRESH: Final = "force_refresh"
SERVICE_SET_HEATING_CURVE: Final = "set_heating_curve"
SERVICE_RESET_LEARNING: Final = "reset_learning"
SERVICE_BOOST_ALL_ROOMS: Final = "boost_all_rooms"
SERVICE_SET_HUB_MODE: Final = "set_hub_mode"

ATTR_ROOM: Final = "room"
ATTR_HEATING_RATE: Final = "heating_rate"
ATTR_LEARNING_SAMPLES: Final = "learning_samples"
ATTR_LAST_LEARNING_UPDATE: Final = "last_learning_update"
ATTR_WINDOW_REASON: Final = "window_reason"
ATTR_HEATING_BLOCKED: Final = "heating_blocked"
ATTR_HEATING_ACTIVE: Final = "heating_active"
ATTR_USE_EARLY_START: Final = "use_early_start"
ATTR_LEARN_HEATING_RATE: Final = "learn_heating_rate"
ATTR_MODE: Final = "mode"
ATTR_TEMPERATURE: Final = "temperature"
ATTR_DURATION_MINUTES: Final = "duration_minutes"

# Climate Entity Attributes for Override Detection
ATTR_TADIY_SCHEDULED_TARGET: Final = "tadiy_scheduled_target"
ATTR_TADIY_OVERRIDE_ACTIVE: Final = "tadiy_override_active"
ATTR_TADIY_OVERRIDE_UNTIL: Final = "tadiy_override_until"
ATTR_TADIY_MODE: Final = "tadiy_mode"
ATTR_TADIY_SCHEDULE_ACTIVE: Final = "tadiy_schedule_active"

UPDATE_INTERVAL: Final = 60

MIN_TARGET_TEMP: Final = 5.0
MAX_TARGET_TEMP: Final = 30.0

MIN_WINDOW_TIMEOUT: Final = 0
MAX_WINDOW_TIMEOUT: Final = 3600

DEFAULT_HEATING_RATE: Final = 1.0
MIN_HEATING_RATE: Final = 0.1
MAX_HEATING_RATE: Final = 10.0

MIN_FROST_PROTECTION: Final = 5.0
MAX_FROST_PROTECTION: Final = 20.0

MIN_BOOST_TEMP: Final = 20.0
MAX_BOOST_TEMP: Final = 35.0

MIN_BOOST_DURATION: Final = 15
MAX_BOOST_DURATION: Final = 180

ICON_WINDOW: Final = "mdi:window-open-variant"
ICON_HEATING: Final = "mdi:fire"
ICON_TEMPERATURE: Final = "mdi:thermometer"
ICON_LEARNING: Final = "mdi:school"
ICON_MODE: Final = "mdi:home-thermometer"
ICON_FROST: Final = "mdi:snowflake"
ICON_BOOST: Final = "mdi:fire-circle"

SENSOR_TYPE_MAIN_TEMP: Final = "main"
SENSOR_TYPE_OUTDOOR_TEMP: Final = "outdoor"
SENSOR_TYPE_WINDOW_STATE: Final = "window_state"
SENSOR_TYPE_HEATING_RATE: Final = "heating_rate"
SENSOR_TYPE_HEALTH: Final = "health"

HEALTH_STATUS_HEALTHY: Final = "Healthy"
HEALTH_STATUS_DEGRADED: Final = "Degraded"
HEALTH_STATUS_CRITICAL: Final = "Critical"

WINDOW_STATE_OPEN_HEATING_STOPPED: Final = "open_heating_stopped"
WINDOW_STATE_OPEN_WITHIN_TIMEOUT: Final = "open_within_timeout"
WINDOW_STATE_CLOSED_COOLDOWN: Final = "closed_cooldown"
WINDOW_STATE_CLOSED: Final = "closed"
