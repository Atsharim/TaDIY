"""Panel for TaDIY integration."""
from __future__ import annotations

import logging

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register TaDIY panel."""
    try:
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
        hass.components.frontend.async_remove_panel("tadiy")
        _LOGGER.info("TaDIY panel unregistered")
    except Exception as err:
        _LOGGER.error("Failed to unregister TaDIY panel: %s", err)
