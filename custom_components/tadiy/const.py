"""Constants for the TaDIY integration."""
from typing import Final

DOMAIN: Final = "tadiy"

MANUFACTURER: Final = "TaDIY"
MODEL_NAME: Final = "Adaptive Climate Orchestrator"

STORAGE_KEY: Final = f"{DOMAIN}_storage"
STORAGE_VERSION: Final = 1

CONF_GLOBAL_WINDOW_OPEN_TIMEOUT: Final = "global_window_open_timeout"
CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT: Final = "global_window_close_timeout"
CONF_GLOBAL_DONT_HEAT_BELOW: Final = "global_dont_heat_below_outdoor"
CONF_GLOBAL_USE_EARLY_START: Final = "global_use_early_start"
CONF_GLOBAL_LEARN_HEATING_RATE: Final = "global_learn_heating_rate"

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
DEFAULT_WINDOW_OPEN_TIMEOUT: Final = 300
DEFAULT_WINDOW_CLOSE_TIMEOUT: Final = 600
DEFAULT_DONT_HEAT_BELOW: Final = 20.0
DEFAULT_TOLERANCE: Final = "auto"
DEFAULT_TARGET_TEMP_STEP: Final = "auto"
DEFAULT_USE_EARLY_START: Final = True
DEFAULT_LEARN_HEATING_RATE: Final = True
DEFAULT_USE_HUMIDITY_COMPENSATION: Final = False

TEMP_STEP_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]
TOLERANCE_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]

SERVICE_FORCE_REFRESH: Final = "force_refresh"
SERVICE_SET_HEATING_CURVE: Final = "set_heating_curve"
SERVICE_RESET_LEARNING: Final = "reset_learning"

ATTR_ROOM: Final = "room"
ATTR_HEATING_RATE: Final = "heating_rate"
ATTR_LEARNING_SAMPLES: Final = "learning_samples"
ATTR_LAST_LEARNING_UPDATE: Final = "last_learning_update"
ATTR_WINDOW_REASON: Final = "window_reason"
ATTR_HEATING_BLOCKED: Final = "heating_blocked"
ATTR_HEATING_ACTIVE: Final = "heating_active"
ATTR_USE_EARLY_START: Final = "use_early_start"
ATTR_LEARN_HEATING_RATE: Final = "learn_heating_rate"

UPDATE_INTERVAL: Final = 60

MIN_TARGET_TEMP: Final = 5.0
MAX_TARGET_TEMP: Final = 30.0
MIN_WINDOW_TIMEOUT: Final = 60
MAX_WINDOW_TIMEOUT: Final = 3600

DEFAULT_HEATING_RATE: Final = 1.0
MIN_HEATING_RATE: Final = 0.1
MAX_HEATING_RATE: Final = 10.0

ICON_WINDOW: Final = "mdi:window-open-variant"
ICON_HEATING: Final = "mdi:fire"
ICON_TEMPERATURE: Final = "mdi:thermometer"
ICON_LEARNING: Final = "mdi:school"

SENSOR_TYPE_MAIN_TEMP: Final = "main"
SENSOR_TYPE_OUTDOOR_TEMP: Final = "outdoor"
SENSOR_TYPE_WINDOW_STATE: Final = "window_state"
SENSOR_TYPE_HEATING_RATE: Final = "heating_rate"

WINDOW_STATE_OPEN_HEATING_STOPPED: Final = "open_heating_stopped"
WINDOW_STATE_OPEN_WITHIN_TIMEOUT: Final = "open_within_timeout"
WINDOW_STATE_CLOSED_COOLDOWN: Final = "closed_cooldown"
WINDOW_STATE_CLOSED: Final = "closed"
