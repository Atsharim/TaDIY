"""Early start / preheating logic for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class HeatUpModel:
    """Room heat-up characteristics (placeholder)."""
    degrees_per_hour: float = 1.0
