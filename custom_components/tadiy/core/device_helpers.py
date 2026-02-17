"""Device info helpers for TaDIY integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import CONF_HUB, DOMAIN, VERSION


def get_device_info(
    entry: ConfigEntry, hass: HomeAssistant | None = None
) -> dict[str, Any]:
    """Get device info for an entry.

    Creates exactly ONE device per config entry.
    Rooms are linked to Hub via via_device.
    """
    is_hub = entry.data.get(CONF_HUB, False)

    device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,
        "manufacturer": "TaDIY",
    }

    if is_hub:
        device_info["model"] = "Adaptive Climate Orchestrator"
        device_info["sw_version"] = VERSION
        device_info["name"] = entry.title
        device_info["suggested_area"] = "!Hub"  # ! prefix in area name sorts to top
    else:
        device_info["model"] = "Room Controller"

        # Link room to hub via via_device
        hub_entry_id = entry.data.get("hub_entry_id")
        if hub_entry_id:
            device_info["via_device"] = (DOMAIN, hub_entry_id)
        elif hass:
            # Fallback: Find hub entry if not in data
            for config_entry in hass.config_entries.async_entries(DOMAIN):
                if config_entry.data.get(CONF_HUB, False):
                    device_info["via_device"] = (DOMAIN, config_entry.entry_id)
                    break

    return device_info
