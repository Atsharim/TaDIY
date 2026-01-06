"""Coordinator for TaDIY - Adaptive Climate Orchestrator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TaDIYCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for TaDIY data management."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),  # Platzhalter
        )
        _LOGGER.debug("TaDIY Coordinator initialized")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data - placeholder for now."""
        _LOGGER.debug("TaDIY Coordinator update (no-op)")
        # Später: hier TRV-/Sensorzustände einsammeln
        return {}
