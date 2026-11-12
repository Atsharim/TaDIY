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

        # Link room to hub via via_device_id or via_device
        target_hub_id = entry.data.get("hub_entry_id")
        if not target_hub_id and hass:
            for config_entry in hass.config_entries.async_entries(DOMAIN):
                if config_entry.data.get(CONF_HUB, False):
                    target_hub_id = config_entry.entry_id
                    break

        if target_hub_id and hass:
            try:
                from homeassistant.helpers import device_registry as dr
                dev_reg = dr.async_get(hass)
                if hasattr(dev_reg, "async_get_device_by_identifier"):
                    hub_device = dev_reg.async_get_device_by_identifier((DOMAIN, target_hub_id))
                else:
                    hub_device = dev_reg.async_get_device(identifiers={(DOMAIN, target_hub_id)})
                if hub_device:
                    device_info["via_device_id"] = hub_device.id
                else:
                    device_info["via_device"] = (DOMAIN, target_hub_id)
            except Exception:
                device_info["via_device"] = (DOMAIN, target_hub_id)
        elif target_hub_id:
            device_info["via_device"] = (DOMAIN, target_hub_id)

    return device_info
