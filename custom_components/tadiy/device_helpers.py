"""Device info helpers for TaDIY integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_HUB,
    DOMAIN,
    MANUFACTURER,
    MODEL_NAME,
    MODEL_ROOM,
)


def get_device_info(entry: ConfigEntry) -> dict[str, Any]:
    """Get device info for an entry.
    
    CRITICAL: This function MUST be used by ALL entity platforms
    to ensure only ONE device is created per config entry!
    """
    is_hub = entry.data.get("is_hub", False)
    
    if is_hub:
        # Hub device
        device_name = entry.title  # Use entry.title directly!
        model = "Adaptive Climate Orchestrator"
    else:
        # Room device
        device_name = entry.title  # Use entry.title directly!
        model = "Room Controller"
    
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,  # CRITICAL: Must match entry.title exactly!
        "manufacturer": "TaDIY",
        "model": "Adaptive Climate Orchestrator" if entry.data.get(CONF_HUB) else "Room Controller",
    }