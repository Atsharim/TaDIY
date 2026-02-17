"""Global debug logging system for TaDIY."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__package__)

class TaDIYLogger:
    """Centralized logger for TaDIY with granular debug levels."""

    def __init__(self, context: Any) -> None:
        """Initialize the logger context."""
        self.context = context
        # context can be a coordinator or a dict

    def debug(self, category: str, message: str, *args: Any) -> None:
        """Log a debug message if the category is enabled."""
        if self._is_enabled(category):
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
            
            # Use INFO level for requested debug logs so they are visible 
            # without requiring global DEBUG level in configuration.yaml
            _LOGGER.info(f"{prefix}{message}", *args)

    def _is_enabled(self, category: str) -> bool:
        """Check if a debug category is enabled in hub config."""
        # 1. Try to get config from raw dict context
        if isinstance(self.context, dict):
            mapping = {
                "rooms": "debug_rooms",
                "hub": "debug_hub",
                "panel": "debug_panel",
                "ui": "debug_ui",
                "cards": "debug_cards"
            }
            config_key = mapping.get(category.lower())
            return self.context.get(config_key, False) if config_key else False

        # 2. Try to get current hub coordinator from hass
        hub = None
        if hasattr(self.context, "hass"):
            from ..const import DOMAIN
            hub = self.context.hass.data.get(DOMAIN, {}).get("hub_coordinator")
        
        # 3. Fallback to passed hub_coordinator
        if not hub and hasattr(self.context, "hub_coordinator"):
            hub = self.context.hub_coordinator
            
        # 4. Fallback to self (if context is the hub)
        if not hub and hasattr(self.context, "config_data"):
            hub = self.context

        if not hub or not hasattr(hub, "config_data"):
            return False
            
        config = hub.config_data
        
        mapping = {
            "rooms": "debug_rooms",
            "hub": "debug_hub",
            "panel": "debug_panel",
            "ui": "debug_ui",
            "cards": "debug_cards"
        }
        
        config_key = mapping.get(category.lower())
        if not config_key:
            return False
            
        return config.get(config_key, False)
