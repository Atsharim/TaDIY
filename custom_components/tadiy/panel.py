"""Panel for TaDIY integration."""
from __future__ import annotations

import logging

from homeassistant.components import panel_custom
from homeassistant.components.frontend import async_remove_panel
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register TaDIY panel."""
    try:
        # Unregister first if exists to avoid "Overwriting panel" error
        if "tadiy" in hass.data.get("frontend_panels", {}):
            await async_remove_panel(hass, "tadiy")
            _LOGGER.debug("Removed existing TaDIY panel before re-registering")

        # Register the panel using the panel_custom component
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path="tadiy",
            webcomponent_name="tadiy-panel",
            sidebar_title="TaDIY",
            sidebar_icon="mdi:home-thermometer",
            module_url=f"/tadiy/tadiy-panel.js?v={VERSION}",
            embed_iframe=False,
            require_admin=False,
            config={
                "domain": DOMAIN,
            },
        )
        _LOGGER.info("TaDIY panel registered successfully")
    except Exception as err:
        _LOGGER.error("Failed to register TaDIY panel: %s", err)


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister TaDIY panel."""
    try:
        # Check if panel exists before removing
        if "tadiy" in hass.data.get("frontend_panels", {}):
            result = async_remove_panel(hass, "tadiy")
            # Only await if result is awaitable
            if result is not None:
                await result
            _LOGGER.info("TaDIY panel unregistered")
        else:
            _LOGGER.debug("TaDIY panel was not registered, skipping unregister")
    except Exception as err:
        _LOGGER.error("Failed to unregister TaDIY panel: %s", err)
