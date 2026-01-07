"""Button platform for TaDIY."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BOOST_DURATION,
    CONF_BOOST_TEMPERATURE,
    DEFAULT_BOOST_DURATION,
    DEFAULT_BOOST_TEMPERATURE,
    DOMAIN,
    ICON_BOOST,
    ICON_LEARNING,
    MANUFACTURER,
    MODEL_NAME,
)
from .coordinator import TaDIYDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY button entities."""
    coordinator: TaDIYDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    entities = []

    # Create Reset Learning + Boost button for each room
    for room in coordinator.rooms:
        entities.extend([
            TaDIYResetLearningButton(
                coordinator,
                config_entry.entry_id,
                room.name,
            ),
            TaDIYBoostButton(
                coordinator,
                config_entry.entry_id,
                room.name,
            ),
        ])

    async_add_entities(entities)
    _LOGGER.info("TaDIY button platform setup complete with %d buttons", len(entities))


class TaDIYResetLearningButton(CoordinatorEntity, ButtonEntity):
    """Button to reset learning data for a room."""

    _attr_icon = ICON_LEARNING

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_name = f"{room_name} Reset Learning"
        self._attr_unique_id = f"{entry_id}_{room_name}_reset_learning"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_press(self) -> None:
        """Handle button press."""
        from .core.early_start import HeatUpModel

        if self._room_name in self.coordinator._heat_models:
            self.coordinator._heat_models[self._room_name] = HeatUpModel(
                room_name=self._room_name
            )
            await self.coordinator.async_save_learning_data()
            await self.coordinator.async_request_refresh()
            
            _LOGGER.info("Learning data reset for room: %s", self._room_name)


class TaDIYBoostButton(CoordinatorEntity, ButtonEntity):
    """Button to boost heating for a room."""

    _attr_icon = ICON_BOOST

    def __init__(
        self,
        coordinator: TaDIYDataUpdateCoordinator,
        entry_id: str,
        room_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._entry_id = entry_id
        self._attr_name = f"{room_name} Boost"
        self._attr_unique_id = f"{entry_id}_{room_name}_boost"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_{room_name}")},
            "name": f"TaDIY {room_name}",
            "manufacturer": MANUFACTURER,
            "model": MODEL_NAME,
        }

    async def async_press(self) -> None:
        """Handle button press - boost this room."""
        boost_temp = DEFAULT_BOOST_TEMPERATURE
        boost_duration = DEFAULT_BOOST_DURATION

        # Try to get values from config
        config_data = self.coordinator.config_data
        boost_temp = config_data.get(CONF_BOOST_TEMPERATURE, DEFAULT_BOOST_TEMPERATURE)
        boost_duration = config_data.get(
            CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION
        )

        _LOGGER.info(
            "Boost activated for room %s: %.1f°C for %d minutes",
            self._room_name,
            boost_temp,
            boost_duration,
        )

        # Find room config
        room_config = None
        for room in self.coordinator.rooms:
            if room.name == self._room_name:
                room_config = room
                break

        if not room_config:
            _LOGGER.error("Room config not found: %s", self._room_name)
            return

        # Set all TRVs to boost temperature
        for trv_entity_id in room_config.trv_entity_ids:
            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": trv_entity_id,
                        "temperature": boost_temp,
                    },
                    blocking=True,
                )
                _LOGGER.debug("Boost set for TRV: %s", trv_entity_id)
            except Exception as err:
                _LOGGER.error("Failed to boost TRV %s: %s", trv_entity_id, err)

        # Store boost info for tracking
        boost_until = datetime.now() + timedelta(minutes=boost_duration)
        if not hasattr(self.coordinator, "_boosts"):
            self.coordinator._boosts = {}
        
        self.coordinator._boosts[self._room_name] = {
            "active": True,
            "temperature": boost_temp,
            "until": boost_until,
        }

        # Update climate entity to reflect boost
        await self.coordinator.async_request_refresh()
