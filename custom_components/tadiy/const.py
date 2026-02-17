"""Constants for TaDIY - Adaptive Climate Orchestrator."""

DOMAIN = "tadiy"

# Configuration keys
CONF_ROOMS = "rooms"
CONF_ROOM_NAME = "room_name"
CONF_TRV_ENTITIES = "trv_entities"
CONF_MAIN_TEMP_SENSOR = "main_temp_sensor"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_OUTDOOR_SENSOR = "outdoor_sensor"
CONF_WINDOW_OPEN_TIMEOUT = "window_open_timeout"
CONF_WINDOW_CLOSE_TIMEOUT = "window_close_timeout"
CONF_DONT_HEAT_BELOW_OUTDOOR = "dont_heat_below_outdoor"
CONF_USE_HUMIDITY = "use_humidity"
CONF_HUMIDITY_THRESHOLD = "humidity_threshold"

# Defaults
DEFAULT_WINDOW_OPEN_TIMEOUT = 300  # 5min
DEFAULT_WINDOW_CLOSE_TIMEOUT = 900  # 15min
DEFAULT_DONT_HEAT_BELOW = 10.0

# Entity categories
ENTITY_CATEGORY_CONFIG = "config"
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"

# HVAC modes
HVAC_MODES = ["off", "heat"]

# Supported features
SUPPORTED_FEATURES = 0b1111111111111111  # All features

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN

# Event topics
MQTT_ROOM_UPDATE = f"{DOMAIN}/room_update"
