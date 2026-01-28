"""Global debug logging system for TaDIY."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__package__)

class TaDIYLogger:
    """Centralized logger for TaDIY with granular debug levels."""

    def __init__(self, coordinator: Any) -> None:
        """Initialize the logger."""
        self.coordinator = coordinator
        # The coordinator can be a RoomCoordinator or HubCoordinator
        # We'll use the hub_coordinator's config if available
        self._hub = getattr(coordinator, "hub_coordinator", None) or coordinator

    def debug(self, category: str, message: str, *args: Any) -> None:
        """Log a debug message if the category is enabled."""
        if self._is_enabled(category):
            # Prefix with category for easier filtering
            prefix = f"[{category.upper()}] "
            if hasattr(self.coordinator, "room_config"):
                prefix += f"({self.coordinator.room_config.name}) "
            
            _LOGGER.debug(f"{prefix}{message}", *args)

    def _is_enabled(self, category: str) -> bool:
        """Check if a debug category is enabled in hub config."""
        if not self._hub or not hasattr(self._hub, "config_data"):
            return False
            
        config = self._hub.config_data
        
        # Mapping categories to config keys
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
