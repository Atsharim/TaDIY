"""TaDIY - IntelliTRV Manager Integration."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tadiy"
PLATFORMS = ["climate"]  # Später: ["climate", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaDIY from a config entry."""
    _LOGGER.info("Setting up TaDIY integration (entry_id: %s)", entry.entry_id)
    
    # Coordinator für zentrale Datenverwaltung
    coordinator = TaDIYCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Im hass.data speichern für Plattformen
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Plattformen laden (aktuell leer)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.info("TaDIY integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading TaDIY integration")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class TaDIYCoordinator(DataUpdateCoordinator):
    """Coordinator für TaDIY Datenverwaltung."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),  # Platzhalter
        )
        self.entry = entry
        _LOGGER.debug("TaDIY Coordinator initialized")
    
    async def _async_update_data(self):
        """Fetch data - aktuell Platzhalter."""
        _LOGGER.debug("Coordinator update triggered (no-op for now)")
        return {}
