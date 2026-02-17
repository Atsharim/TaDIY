"""Core functionality for TaDIY integration."""

from __future__ import annotations

from .early_start import EarlyStartCalculator, HeatUpModel
from .temperature import SensorReading, calculate_fused_temperature
from .window import WindowDetector, WindowState

__all__ = [
    "EarlyStartCalculator",
    "HeatUpModel",
    "SensorReading",
    "WindowDetector",
    "WindowState",
    "calculate_fused_temperature",
]
