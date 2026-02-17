"""Button platform for TaDIY integration."""

from __future__ import annotations
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_BOOST
from .core.device_helpers import get_device_info

_LOGGER = logging.getLogger(__name__)

ROOM_BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="force_refresh", name="Force Refresh", icon="mdi:refresh"
    ),
    ButtonEntityDescription(
        key="reset_learning", name="Reset Learning Data", icon="mdi:brain"
    ),
)

HUB_BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="force_refresh_all", name="Force Refresh All", icon="mdi:refresh"
    ),
    ButtonEntityDescription(
        key="reset_all_learning", name="Reset All Learning Data", icon="mdi:brain"
    ),
    ButtonEntityDescription(
        key="boost_all_rooms", name="Boost All Rooms", icon=ICON_BOOST
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY button entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[ButtonEntity] = []

    if entry_type == "hub":
        for description in HUB_BUTTON_TYPES:
            entities.append(TaDIYHubButton(coordinator, description, entry))
        _LOGGER.info("Added %d hub button entities", len(entities))
    elif entry_type == "room":
        room_name = coordinator.room_config.name
        for description in ROOM_BUTTON_TYPES:
            entities.append(TaDIYRoomButton(coordinator, description, entry, room_name))
        _LOGGER.info("Added %d room button entities for %s", len(entities), room_name)

    async_add_entities(entities)


class TaDIYHubButton(CoordinatorEntity, ButtonEntity):
    """Representation of a TaDIY Hub Button."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator, description: ButtonEntityDescription, entry: ConfigEntry
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "force_refresh_all":
            await self.coordinator.async_request_refresh()
            for entry_id, data in self.hass.data[DOMAIN].items():
                if data.get("type") == "room":
                    await data["coordinator"].async_request_refresh()
        elif self.entity_description.key == "reset_all_learning":
            from .core.early_start import HeatUpModel

            for room_name in list(self.coordinator.heat_models.keys()):
                self.coordinator.heat_models[room_name] = HeatUpModel(
                    room_name=room_name
                )
            await self.coordinator.async_save_learning_data()
        elif self.entity_description.key == "boost_all_rooms":
            await self.hass.services.async_call(
                DOMAIN, "boost_all_rooms", {}, blocking=True
            )


class TaDIYRoomButton(CoordinatorEntity, ButtonEntity):
    """Representation of a TaDIY Room Button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: ButtonEntityDescription,
        entry: ConfigEntry,
        room_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._room_name = room_name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, coordinator.hass)

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "force_refresh":
            await self.coordinator.async_request_refresh()
        elif self.entity_description.key == "reset_learning":
            if self.coordinator.hub_coordinator:
                from .core.early_start import HeatUpModel

                if self._room_name in self.coordinator.hub_coordinator.heat_models:
                    self.coordinator.hub_coordinator.heat_models[self._room_name] = (
                        HeatUpModel(room_name=self._room_name)
                    )
                    await self.coordinator.hub_coordinator.async_save_learning_data()
