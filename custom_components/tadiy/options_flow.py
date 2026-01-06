"""Options flow for TaDIY."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TaDIROptionsFlowHandler(config_entries.OptionsFlow):
    """Handle TaDIY options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Room management overview."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(["add_room"]),
            }),
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add/configure room."""
        if user_input is not None:
            room_config = {
                "room_name": user_input["room_name"],
                "trv_entities": [e.strip() for e in user_input["trv_entities"].split(",")],
                "main_temp_sensor": user_input["main_temp_sensor"],
                "window_sensors": [e.strip() for e in user_input["window_sensors"].split(",")] if user_input["window_sensors"] else [],
                "weather_entity": user_input.get("weather_entity", ""),
                "outdoor_sensor": user_input.get("outdoor_sensor", ""),
                "window_open_timeout": int(user_input["window_open_timeout"]),
                "window_close_timeout": int(user_input["window_close_timeout"]),
                "dont_heat_below_outdoor": float(user_input["dont_heat_below_outdoor"]),
            }
            # Merge mit bestehenden Options
            options = dict(self.config_entry.options)
            options.setdefault("rooms", []).append(room_config)
            
            _LOGGER.info("Room config added: %s", room_config["room_name"])
            return self.async_create_entry(title="Rooms", data=options)

        # Entity-Listen abrufen
        registry = er.async_get(self.hass)
        climates = [entity.entity_id for entity in er.async_all(self.hass) if entity.domain == "climate"]
        temp_sensors = [entity.entity_id for entity in er.async_all(self.hass) 
                       if entity.domain == "sensor" and "temp" in entity.entity_id.lower()]
        window_sensors = [entity.entity_id for entity in er.async_all(self.hass)
                         if entity.domain == "binary_sensor" and "fenster" in entity.entity_id.lower()]
        weather_entities = [""] + [entity.entity_id for entity in er.async_all(self.hass) if entity.domain == "weather"]

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema({
                vol.Required("room_name"): str,
                vol.Required("trv_entities"): str,
                vol.Required("main_temp_sensor"): vol.In(temp_sensors),
                vol.Optional("window_sensors", default=""): str,
                vol.Optional("weather_entity"): vol.In(weather_entities),
                vol.Optional("outdoor_sensor"): vol.In([""] + temp_sensors),
                vol.Optional("window_open_timeout", default=300): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=3600)
                ),
                vol.Optional("window_close_timeout", default=900): vol.All(
                    vol.Coerce(int), vol.Range(min=60, max=7200)
                ),
                vol.Optional("dont_heat_below_outdoor", default=10.0): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=30.0)
                ),
            }),
            description_placeholders={
                "examples": "TRVs: climate.thermostat_wohnbereich_rechts,climate.thermostat_wohnbereich_links",
                "timeout_hint": "Fenster offen: Zeit bis Heizung stoppt | Fenster zu: Wartezeit bis Wiederanfahren"
            },
        )
