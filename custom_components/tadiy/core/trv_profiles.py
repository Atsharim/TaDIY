"""TRV profiles for different thermostat manufacturers.

Provides manufacturer-specific configuration for TRV communication,
including calibration attributes, HVAC mode support, and fallback
strategies for missing features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class TRVProfile:
    """Configuration profile for a specific TRV type."""

    name: str
    manufacturer: str
    hvac_modes: list[str] = field(default_factory=lambda: ["heat", "off"])
    supports_auto: bool = False
    calibration_attr: str | None = None
    calibration_range: tuple[float, float] = (0.0, 0.0)
    temperature_attr: str = "temperature"
    valve_position_attr: str | None = None
    precision: float = 0.5
    window_detection_attr: str | None = None
    supports_eco_mode: bool = False
    min_temp: float = 5.0
    max_temp: float = 30.0


# Built-in profiles
PROFILES: dict[str, TRVProfile] = {
    "moes": TRVProfile(
        name="moes",
        manufacturer="Moes",
        hvac_modes=["heat", "off"],
        supports_auto=False,
        calibration_attr="local_temperature_calibration",
        calibration_range=(-9.0, 9.0),
        temperature_attr="temperature",
        valve_position_attr=None,
        precision=0.5,
        window_detection_attr="window_detection",
        supports_eco_mode=True,
        min_temp=5.0,
        max_temp=30.0,
    ),
    "sonoff": TRVProfile(
        name="sonoff",
        manufacturer="Sonoff",
        hvac_modes=["heat", "off", "auto"],
        supports_auto=True,
        calibration_attr="local_temperature_calibration",
        calibration_range=(-7.0, 7.0),
        temperature_attr="temperature",
        valve_position_attr=None,
        precision=0.5,
        window_detection_attr=None,
        supports_eco_mode=False,
        min_temp=5.0,
        max_temp= 30.0,
    ),
    "generic": TRVProfile(
        name="generic",
        manufacturer="Generic",
        hvac_modes=["heat", "off"],
        supports_auto=False,
        calibration_attr=None,
        calibration_range=(0.0, 0.0),
        temperature_attr="temperature",
        valve_position_attr=None,
        precision=0.5,
        window_detection_attr=None,
        supports_eco_mode=False,
        min_temp=5.0,
        max_temp=30.0,
    ),
}


def detect_trv_profile(entity_id: str, state: Any) -> str:
    """Auto-detect TRV manufacturer profile from entity attributes.

    Detection strategy (in order):
    1. Check for known calibration attribute names
    2. Check manufacturer/model attributes
    3. Fall back to generic
    """
    if state is None:
        return "generic"

    attrs = state.attributes or {}

    # Moes detection: unique calibration attribute
    if "local_temperature_calibration" in attrs:
        _LOGGER.debug("TRV %s detected as Moes (calibration attr)", entity_id)
        return "moes"

    # Check manufacturer string
    manufacturer = str(attrs.get("manufacturer", "")).lower()
    model = str(attrs.get("model", "")).lower()
    friendly = str(attrs.get("friendly_name", "")).lower()

    if "moes" in manufacturer or "moes" in model or "_moes" in entity_id.lower():
        _LOGGER.debug("TRV %s detected as Moes (name match)", entity_id)
        return "moes"

    if (
        "sonoff" in manufacturer
        or "ewelink" in manufacturer
        or "sonoff" in model
        or "_sonoff" in entity_id.lower()
    ):
        _LOGGER.debug("TRV %s detected as Sonoff (name match)", entity_id)
        return "sonoff"

    # Check HVAC modes for Sonoff-style devices (support auto mode)
    hvac_modes = attrs.get("hvac_modes", [])
    if "auto" in hvac_modes and "heat" in hvac_modes:
        _LOGGER.debug("TRV %s detected as Sonoff (auto mode support)", entity_id)
        return "sonoff"

    _LOGGER.debug("TRV %s: no profile match, using generic", entity_id)
    return "generic"


def get_profile(name: str) -> TRVProfile:
    """Get a TRV profile by name, falling back to generic."""
    return PROFILES.get(name, PROFILES["generic"])
