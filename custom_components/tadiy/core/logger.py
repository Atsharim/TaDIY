"""Global debug logging system for TaDIY."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class TaDIYLogger:
    """Centralized logger for TaDIY with granular debug levels."""

    # Category to config key mapping
    CATEGORY_MAPPING = {
        "rooms": "debug_rooms",
        "hub": "debug_hub",
        "panel": "debug_panel",
        "ui": "debug_ui",
        "cards": "debug_cards",
        "trv": "debug_trv",
        "sensors": "debug_sensors",
        "schedule": "debug_schedule",
        "heating": "debug_heating",
        "calibration": "debug_calibration",
        "early_start": "debug_early_start",
        "verbose": "debug_verbose",
    }

    def __init__(self, context: Any) -> None:
        """Initialize the logger context."""
        self.context = context
        # context can be a coordinator or a dict

    def debug(self, category: str, message: str, *args: Any) -> None:
        """Log a debug message if the category is enabled."""
        enabled = self._is_enabled(category)
        if enabled:
            # Prefix with category for easier filtering
            prefix = f"[{category.upper()}] "

            # Try to get room name from context
            room_name = None
            if hasattr(self.context, "room_config"):
                room_name = self.context.room_config.name
            elif isinstance(self.context, dict) and "room_name" in self.context:
                room_name = self.context["room_name"]

            if room_name:
                prefix += f"({room_name}) "

            _LOGGER.debug(prefix + message, *args)

    def _is_enabled(self, category: str) -> bool:
        """Check if a debug category is enabled in hub config."""
        config_key = self.CATEGORY_MAPPING.get(category.lower())
        if not config_key:
            return False

        # Get the config dict
        config = self._get_config()
        if not config:
            return False

        # Check if verbose mode is enabled (enables all categories)
        if config.get("debug_verbose", False):
            return True

        return config.get(config_key, False)

    def _get_config(self) -> dict | None:
        """Get the config dictionary from context."""
        # 1. Try to get config from raw dict context
        if isinstance(self.context, dict):
            return self.context

        # 2. Try to get hub from coordinator's hub_coordinator attribute
        hub = getattr(self.context, "hub_coordinator", None)

        # 3. If context IS the hub (has config_data attribute)
        if not hub and hasattr(self.context, "config_data"):
            hub = self.context

        # 4. Try to get from hass.data
        if not hub and hasattr(self.context, "hass"):
            try:
                from ..const import DOMAIN

                domain_data = self.context.hass.data.get(DOMAIN)
                if domain_data and isinstance(domain_data, dict):
                    hub = domain_data.get("hub_coordinator")
            except Exception:
                pass

        if not hub or not hasattr(hub, "config_data"):
            return None

        config = hub.config_data
        if not isinstance(config, dict):
            return None

        return config
