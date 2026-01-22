"""Weather-compensated heating curve for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass
import logging

_LOGGER = logging.getLogger(__name__)


@dataclass
class HeatingCurveConfig:
    """Configuration for weather-compensated heating curve."""

    outdoor_reference_temp: float = 0.0
    indoor_target_temp: float = 21.0
    curve_slope: float = 0.5
    min_indoor_target: float = 15.0
    max_indoor_target: float = 24.0


class HeatingCurve:
    """Weather-compensated heating curve calculator."""

    def __init__(self, config: HeatingCurveConfig | None = None) -> None:
        """Initialize heating curve.

        Args:
            config: Heating curve configuration
        """
        self.config = config or HeatingCurveConfig()

    def calculate_target(
        self,
        outdoor_temp: float,
        base_target: float,
    ) -> float:
        """Calculate weather-compensated target temperature.

        Args:
            outdoor_temp: Current outdoor temperature (°C)
            base_target: Base target from schedule (°C)

        Returns:
            Adjusted target temperature (°C)
        """
        outdoor_delta = outdoor_temp - self.config.outdoor_reference_temp
        target_adjustment = -1 * self.config.curve_slope * outdoor_delta

        adjusted_target = base_target + target_adjustment

        adjusted_target = max(
            self.config.min_indoor_target,
            min(self.config.max_indoor_target, adjusted_target),
        )

        _LOGGER.debug(
            "Heating curve: outdoor=%.1f°C, base_target=%.1f°C, "
            "adjustment=%.1f°C, final=%.1f°C",
            outdoor_temp,
            base_target,
            target_adjustment,
            adjusted_target,
        )

        return round(adjusted_target, 1)

    def get_curve_points(
        self, outdoor_range: tuple[float, float]
    ) -> list[tuple[float, float]]:
        """Generate heating curve points for visualization.

        Args:
            outdoor_range: (min_outdoor, max_outdoor) in °C

        Returns:
            List of (outdoor_temp, indoor_target) tuples
        """
        min_outdoor, max_outdoor = outdoor_range
        points = []

        for outdoor in range(int(min_outdoor), int(max_outdoor) + 1):
            indoor = self.calculate_target(
                float(outdoor),
                self.config.indoor_target_temp,
            )
            points.append((outdoor, indoor))

        return points
