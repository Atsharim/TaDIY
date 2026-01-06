"""Options flow for TaDIY."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .models.room import RoomConfig

_LOGGER = logging.getLogger(__name__)


class TaDIROptionsFlowHandler(config_entries.OptionsFlow):
    """Handle TaDIY options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.rooms: list[RoomConfig] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage rooms."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(["add_room", "edit_room"]),
            }),
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        if user_input is not None:
            # Später: Daten validieren und speichern
            return self.async_create_entry(title="Rooms", data=self.options)

        # Climate-Entities zum Auswählen anbieten
        registry = er.async_get(self.hass)
        climates = [
            entity.attributes.get("friendly_name", entity.entity_id)
            for entity in er.async_all(self.hass)
            if entity.domain == ClimateEntity.DOMAIN
        ]

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema({
                vol.Required("room_name"): str,
                vol.Required("trv_entity"): vol.In(climates),
                vol.Optional("temp_sensor_entity"): str,
            }),
            description_placeholders={
                "hint": "Wähle dein TRV und optionale Temperatursensoren"
            },
        )
