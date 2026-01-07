"""Constants for the TaDIY integration."""
from typing import Final

DOMAIN: Final = "tadiy"

# Storage
STORAGE_KEY: Final = f"{DOMAIN}.storage"
STORAGE_VERSION: Final = 1

# Config entry keys
CONF_NAME: Final = "name"
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

# New aliases for better UX
CONF_WINDOW_OPEN_DELAY: Final = CONF_WINDOW_OPEN_TIMEOUT
CONF_WINDOW_CLOSE_DELAY: Final = CONF_WINDOW_CLOSE_TIMEOUT

# Default values
DEFAULT_NAME: Final = "TaDIY Hub"
DEFAULT_WINDOW_OPEN_TIMEOUT: Final = 300  # 5 minutes
DEFAULT_WINDOW_CLOSE_TIMEOUT: Final = 600  # 10 minutes
DEFAULT_DONT_HEAT_BELOW: Final = 20.0
DEFAULT_TOLERANCE: Final = "auto"
DEFAULT_TARGET_TEMP_STEP: Final = "auto"

# Options for selectors
TEMP_STEP_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]
TOLERANCE_OPTIONS: Final = ["auto", "0.1", "0.2", "0.25", "0.5", "1.0"]

# Service names
SERVICE_FORCE_REFRESH: Final = "force_refresh"

# Update interval
UPDATE_INTERVAL: Final = 30  # seconds
