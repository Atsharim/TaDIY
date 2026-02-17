"""Select platform for TaDIY integration."""

from __future__ import annotations
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ICON_MODE,
)

_LOGGER = logging.getLogger(__name__)


HUB_SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="hub_mode",
        name="Hub Mode",
        icon=ICON_MODE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaDIY select entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    entry_type = entry_data.get("type")

    entities: list[SelectEntity] = []

    if entry_type == "hub":
        # Hub selects
        for description in HUB_SELECT_TYPES:
            entities.append(
                TaDIYHubSelect(
                    coordinator=coordinator,
                    description=description,
                    entry_id=entry.entry_id,
                )
            )
        _LOGGER.info("Added %d hub select entities", len(entities))

    elif entry_type == "room":
        # Room doesn't have select entities currently
        _LOGGER.debug("Room entry - no select entities")
        return

    async_add_entities(entities)


class TaDIYHubSelect(CoordinatorEntity, SelectEntity):
    """Representation of a TaDIY Hub Select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: SelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_hub_{description.key}"
        self._attr_name = description.name

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
        }

    @property
    def options(self) -> list[str]:
        """Return available options dynamically from coordinator."""
        if self.entity_description.key == "hub_mode":
            return self.coordinator.get_custom_modes()
        return []

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        if self.entity_description.key == "hub_mode":
            return self.coordinator.get_hub_mode()
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self.entity_description.key == "hub_mode":
            available_modes = self.coordinator.get_custom_modes()
            if option in available_modes:
                self.coordinator.set_hub_mode(option)
                await self.coordinator.async_save_schedules()
                await self.coordinator.async_request_refresh()
                _LOGGER.info("Hub mode changed to: %s", option)
            else:
                _LOGGER.error(
                    "Invalid hub mode: %s (available: %s)", option, available_modes
                )

        self.async_write_ha_state()
