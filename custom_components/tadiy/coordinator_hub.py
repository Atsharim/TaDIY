"""Coordinator for TaDIY Hub."""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    CONF_GLOBAL_DONT_HEAT_BELOW,
    CONF_GLOBAL_EARLY_START_MAX,
    CONF_GLOBAL_EARLY_START_OFFSET,
    CONF_GLOBAL_LEARN_HEATING_RATE,
    CONF_GLOBAL_USE_EARLY_START,
    CONF_GLOBAL_WINDOW_CLOSE_TIMEOUT,
    CONF_GLOBAL_WINDOW_OPEN_TIMEOUT,
    DEFAULT_DONT_HEAT_BELOW,
    DEFAULT_EARLY_START_MAX,
    DEFAULT_EARLY_START_OFFSET,
    DEFAULT_FROST_PROTECTION_TEMP,
    DEFAULT_HUB_MODE,
    DEFAULT_LEARN_HEATING_RATE,
    DEFAULT_USE_EARLY_START,
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_KEY_SCHEDULES,
    STORAGE_VERSION,
    STORAGE_VERSION_SCHEDULES,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TaDIYHubCoordinator(DataUpdateCoordinator):
    """Coordinator for TaDIY Hub (global configuration)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config_data: dict[str, Any],
    ) -> None:
        """Initialize the hub coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="TaDIY Hub",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry_id = entry_id
        self.config_data = config_data
        
        # Hub state
        self.hub_mode = DEFAULT_HUB_MODE
        self.frost_protection_temp = DEFAULT_FROST_PROTECTION_TEMP
        
        # Global settings - NEU: für Zugriff aus Room Coordinators
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
        }
        
        # Storage
        self.learning_store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry_id}",
        )
        self.schedule_store = Store(
            hass,
            STORAGE_VERSION_SCHEDULES,
            f"{STORAGE_KEY_SCHEDULES}_{entry_id}",
        )
        
        # Overrides tracking
        self.overrides: dict[str, dict[str, Any]] = {}
        
        # Heat models
        self.heat_models: dict[str, Any] = {}
        
        # Schedule engine
        self.schedule_engine: Any = None
        
        self.data = {
            "hub": True,
            "name": config_data.get("name", "TaDIY Hub"),
            "hub_mode": self.hub_mode,
            "frost_protection_temp": self.frost_protection_temp,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from coordinator."""
        try:
            # Hub coordinator mainly holds global config
            # Update state from entities if available
            self._update_hub_mode()
            self._update_frost_protection_temp()
            
            # Update global settings from config_data
            self._update_global_settings()
            
            self.data.update({
                "hub": True,
                "name": self.config_data.get("name", "TaDIY Hub"),
                "hub_mode": self.hub_mode,
                "frost_protection_temp": self.frost_protection_temp,
            })
            
            return self.data
        except Exception as err:
            raise UpdateFailed(f"Error updating TaDIY Hub: {err}") from err

    def _update_global_settings(self) -> None:
        """Update global settings from config_data."""
        self.global_settings.update({
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
        })

    def _update_hub_mode(self) -> None:
        """Update hub mode from select entity if available."""
        select_entity_id = f"select.{DOMAIN}_hub_mode"
        select_state = self.hass.states.get(select_entity_id)
        
        if select_state and select_state.state in (
            "normal",
            "homeoffice",
            "vacation",
            "party",
        ):
            self.hub_mode = select_state.state
            _LOGGER.debug("Hub mode updated to: %s", self.hub_mode)

    def _update_frost_protection_temp(self) -> None:
        """Update frost protection temperature from number entity if available."""
        number_entity_id = f"number.{DOMAIN}_frost_protection"
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
            # Load hub settings
            hub_data = data.get("hub", {})
            self.hub_mode = hub_data.get("current_mode", DEFAULT_HUB_MODE)
            self.frost_protection_temp = hub_data.get(
                "frost_protection_temp",
                DEFAULT_FROST_PROTECTION_TEMP,
            )
            
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
            # Learning data structure: {room_name: model_data}
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
        """Set hub mode."""
        if mode in ("normal", "homeoffice", "vacation", "party"):
            self.hub_mode = mode
            _LOGGER.debug("Hub mode set to: %s", mode)
        else:
            _LOGGER.warning("Invalid hub mode: %s", mode)

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

    def register_heat_model(self, room_name: str, model: Any) -> None:
        """Register a heat model for a room."""
        self.heat_models[room_name] = model
        _LOGGER.debug("Heat model registered for room: %s", room_name)

    def get_heat_model(self, room_name: str) -> Any | None:
        """Get heat model for a room."""
        return self.heat_models.get(room_name)