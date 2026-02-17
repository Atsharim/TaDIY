"""Weather-based predictive heating control for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Weather prediction constants
FORECAST_HORIZON_HOURS = 24  # How far ahead to look
COLD_FRONT_THRESHOLD = -3.0  # °C drop to trigger pre-heating
WARM_FRONT_THRESHOLD = 3.0  # °C rise to trigger heating reduction
PREDICTION_ADVANCE_HOURS = 2  # How many hours in advance to react


@dataclass
class WeatherForecast:
    """Weather forecast data point."""

    time: datetime
    temperature: float
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "time": self.time.isoformat(),
            "temperature": self.temperature,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherForecast:
        """Create from dictionary."""
        return cls(
            time=datetime.fromisoformat(data["time"]),
            temperature=data["temperature"],
            condition=data.get("condition"),
        )


@dataclass
class WeatherPrediction:
    """Weather-based heating prediction."""

    predicted_event: str  # "cold_front", "warm_front", "stable", "unknown"
    temperature_change: float  # Expected temperature change in °C
    event_time: datetime | None  # When the event is expected
    recommendation: str  # "preheat", "reduce", "maintain"
    adjustment_celsius: float  # Recommended temperature adjustment

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "predicted_event": self.predicted_event,
            "temperature_change": self.temperature_change,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "recommendation": self.recommendation,
            "adjustment_celsius": self.adjustment_celsius,
        }


class WeatherPredictor:
    """Predict heating adjustments based on weather forecasts."""

    def __init__(self, hass: HomeAssistant, weather_entity_id: str) -> None:
        """
        Initialize weather predictor.

        Args:
            hass: Home Assistant instance
            weather_entity_id: Weather entity ID to use for forecasts
        """
        self.hass = hass
        self.weather_entity_id = weather_entity_id
        self._last_forecast: list[WeatherForecast] = []
        self._last_update: datetime | None = None

    async def async_update_forecast(self) -> bool:
        """
        Update weather forecast from Home Assistant.

        Returns:
            True if forecast was updated successfully
        """
        if not self.weather_entity_id:
            return False

        weather_state = self.hass.states.get(self.weather_entity_id)
        if not weather_state:
            _LOGGER.debug(
                "Weather entity %s not found or not yet available",
                self.weather_entity_id,
            )
            return False

        # Get forecast attribute
        forecast_data = weather_state.attributes.get("forecast")
        if not forecast_data:
            _LOGGER.debug("No forecast data available from %s", self.weather_entity_id)
            return False

        # Parse forecast into WeatherForecast objects
        forecasts = []
        now = dt_util.utcnow()
        cutoff_time = now + timedelta(hours=FORECAST_HORIZON_HOURS)

        for entry in forecast_data:
            # Parse datetime (can be string or datetime)
            forecast_time = entry.get("datetime")
            if isinstance(forecast_time, str):
                try:
                    forecast_time = datetime.fromisoformat(forecast_time)
                except (ValueError, TypeError):
                    continue
            elif not isinstance(forecast_time, datetime):
                continue

            # Only keep forecasts within our horizon
            if forecast_time > cutoff_time:
                continue

            # Get temperature
            temp = entry.get("temperature")
            if temp is None:
                continue

            try:
                temp = float(temp)
            except (ValueError, TypeError):
                continue

            forecasts.append(
                WeatherForecast(
                    time=forecast_time,
                    temperature=temp,
                    condition=entry.get("condition"),
                )
            )

        if forecasts:
            self._last_forecast = sorted(forecasts, key=lambda f: f.time)
            self._last_update = now
            _LOGGER.debug(
                "Updated weather forecast: %d data points over %d hours",
                len(forecasts),
                FORECAST_HORIZON_HOURS,
            )
            return True

        return False

    def predict_heating_adjustment(
        self,
        current_outdoor_temp: float,
    ) -> WeatherPrediction:
        """
        Predict heating adjustment based on weather forecast.

        Args:
            current_outdoor_temp: Current outdoor temperature

        Returns:
            Weather prediction with recommended adjustments
        """
        # Default prediction if no forecast available
        if not self._last_forecast:
            return WeatherPrediction(
                predicted_event="unknown",
                temperature_change=0.0,
                event_time=None,
                recommendation="maintain",
                adjustment_celsius=0.0,
            )

        now = dt_util.utcnow()
        advance_time = now + timedelta(hours=PREDICTION_ADVANCE_HOURS)

        # Find significant temperature changes in forecast
        max_temp_change = 0.0
        event_time = None
        event_type = "stable"

        for i, forecast in enumerate(self._last_forecast):
            # Skip past forecasts
            if forecast.time < now:
                continue

            # Calculate temperature change from current
            temp_change = forecast.temperature - current_outdoor_temp

            # Check if this is within our advance window
            if forecast.time <= advance_time:
                # Cold front detection (temperature dropping)
                if temp_change <= COLD_FRONT_THRESHOLD:
                    if abs(temp_change) > abs(max_temp_change):
                        max_temp_change = temp_change
                        event_time = forecast.time
                        event_type = "cold_front"

                # Warm front detection (temperature rising)
                elif temp_change >= WARM_FRONT_THRESHOLD:
                    if abs(temp_change) > abs(max_temp_change):
                        max_temp_change = temp_change
                        event_time = forecast.time
                        event_type = "warm_front"

        # Determine recommendation and adjustment
        if event_type == "cold_front":
            # Cold front coming - preheat to compensate
            recommendation = "preheat"
            # Adjust target up by fraction of expected drop
            adjustment = abs(max_temp_change) * 0.3  # 30% of expected drop
            adjustment = min(adjustment, 2.0)  # Max +2°C adjustment

        elif event_type == "warm_front":
            # Warm front coming - reduce heating
            recommendation = "reduce"
            # Adjust target down by fraction of expected rise
            adjustment = -abs(max_temp_change) * 0.3  # 30% of expected rise
            adjustment = max(adjustment, -2.0)  # Max -2°C adjustment

        else:
            # Stable weather
            recommendation = "maintain"
            adjustment = 0.0

        prediction = WeatherPrediction(
            predicted_event=event_type,
            temperature_change=max_temp_change,
            event_time=event_time,
            recommendation=recommendation,
            adjustment_celsius=adjustment,
        )

        if adjustment != 0.0:
            _LOGGER.info(
                "Weather prediction: %s (%.1f°C change at %s), "
                "recommendation: %s (%.1f°C adjustment)",
                event_type,
                max_temp_change,
                event_time.strftime("%H:%M") if event_time else "unknown",
                recommendation,
                adjustment,
            )

        return prediction

    def get_temperature_trend(self, hours: int = 6) -> str:
        """
        Get temperature trend over next N hours.

        Args:
            hours: Number of hours to analyze

        Returns:
            Trend description: "rising", "falling", "stable"
        """
        if not self._last_forecast or len(self._last_forecast) < 2:
            return "stable"

        now = dt_util.utcnow()
        end_time = now + timedelta(hours=hours)

        # Get forecasts within time window
        relevant_forecasts = [
            f for f in self._last_forecast if now <= f.time <= end_time
        ]

        if len(relevant_forecasts) < 2:
            return "stable"

        # Calculate average temperature change
        start_temp = relevant_forecasts[0].temperature
        end_temp = relevant_forecasts[-1].temperature
        temp_change = end_temp - start_temp

        if temp_change > 1.0:
            return "rising"
        elif temp_change < -1.0:
            return "falling"
        else:
            return "stable"

    def get_forecast_summary(self) -> dict[str, Any]:
        """
        Get summary of current weather forecast.

        Returns:
            Dictionary with forecast summary
        """
        if not self._last_forecast:
            return {
                "available": False,
                "last_update": None,
                "forecast_points": 0,
            }

        temps = [f.temperature for f in self._last_forecast]
        return {
            "available": True,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "forecast_points": len(self._last_forecast),
            "min_temp": min(temps),
            "max_temp": max(temps),
            "avg_temp": sum(temps) / len(temps),
            "trend": self.get_temperature_trend(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "weather_entity_id": self.weather_entity_id,
            "last_forecast": [f.to_dict() for f in self._last_forecast],
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    @classmethod
    def from_dict(cls, hass: HomeAssistant, data: dict[str, Any]) -> WeatherPredictor:
        """Create from dictionary."""
        predictor = cls(hass, data["weather_entity_id"])
        predictor._last_forecast = [
            WeatherForecast.from_dict(f) for f in data.get("last_forecast", [])
        ]
        if data.get("last_update"):
            predictor._last_update = datetime.fromisoformat(data["last_update"])
        return predictor
