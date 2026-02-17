"""Coordinator for TaDIY integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ROOMS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TaDIYCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """TaDIY data coordinator."""

    def __init__(self, hass: HomeAssistant, entry_id: str, rooms: list[dict]) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry_id = entry_id
        self.rooms = rooms

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors."""
        try:
            data = {"rooms": {}}
            
            for room in self.rooms:
                room_name = room.get("room_name", "Unknown")
                room_data = await self._fetch_room_data(room)
                data["rooms"][room_name] = room_data
            
            return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching TaDIY data: {err}") from err

    async def _fetch_room_data(self, room: dict) -> dict[str, Any]:
        """Fetch data for a single room."""
        room_data = {
            "main_temp": None,
            "outdoor_temp": None,
            "window_state": "closed",
            "trv_states": [],
        }

        # Get main temperature
        main_temp_sensor = room.get("main_temp_sensor")
        if main_temp_sensor:
            state = self.hass.states.get(main_temp_sensor)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    room_data["main_temp"] = float(state.state)
                except (ValueError, TypeError):
                    pass

        # Get outdoor temperature
        outdoor_sensor = room.get("outdoor_sensor")
        if outdoor_sensor:
            state = self.hass.states.get(outdoor_sensor)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    room_data["outdoor_temp"] = float(state.state)
                except (ValueError, TypeError):
                    pass

        # Check window sensors
        window_sensors = room.get("window_sensors", [])
        if window_sensors:
            any_open = False
            for sensor in window_sensors:
                state = self.hass.states.get(sensor)
                if state and state.state == "on":
                    any_open = True
                    break
            room_data["window_state"] = "open" if any_open else "closed"

        # Get TRV states
        trv_entities = room.get("trv_entities", [])
        for trv in trv_entities:
            state = self.hass.states.get(trv)
            if state:
                room_data["trv_states"].append({
                    "entity_id": trv,
                    "state": state.state,
                    "attributes": dict(state.attributes),
                })

        return room_data
