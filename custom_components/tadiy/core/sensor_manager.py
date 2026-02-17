"""Sensor management logic for TaDIY.

Provides temperature reading, fusion, and smoothing for room sensors.
Includes a dual-stage filter (spike rejection + EMA) to suppress sensor
jitter and prevent erratic heating decisions.
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any, NamedTuple

_LOGGER = logging.getLogger(__package__)

TRV_SENSOR_WEIGHT_DEFAULT = 0.3

# EMA smoothing factor: lower = more smoothing, higher = more responsive.
# 0.2 means 20% new value, 80% previous — filters ±0.1°C jitter while
# still tracking real changes within 3-4 update cycles (~90-120s).
SENSOR_EMA_ALPHA: float = 0.2

# Maximum allowed single-step deviation before treating as spike (°C).
# Readings that jump more than this from the EMA are dampened, not
# immediately adopted.  A real 1°C jump in 30s is physically impossible
# for a room — it's always sensor noise or a restart.
SPIKE_THRESHOLD: float = 1.0

# When a spike is detected, use a much slower alpha to absorb it gradually.
SPIKE_DAMPENING_ALPHA: float = 0.05


class SensorReading(NamedTuple):
    """Container for temperature sensor readings."""

    entity_id: str
    temperature: float
    weight: float = 1.0


def calculate_dynamic_trv_weight(main_temp: float, trv_temp: float) -> float:
    """Calculate dynamic TRV sensor weight based on deviation from main sensor.

    When the TRV sensor is close to the main sensor, it's more trustworthy.
    When it deviates strongly (heated by radiator), reduce its influence.
    """
    diff = abs(main_temp - trv_temp)
    if diff < 0.5:
        return 1.0  # Both sensors agree
    if diff < 1.5:
        return 0.5  # Moderate deviation
    return 0.1  # Strong deviation — TRV biased by radiator heat


def calculate_fused_temperature(readings: list[SensorReading]) -> float | None:
    """Calculate weighted average temperature from multiple sensors."""
    if not readings:
        return None

    total_weight = sum(r.weight for r in readings)
    if total_weight == 0:
        return None

    weighted_sum = sum(r.temperature * r.weight for r in readings)
    return round(weighted_sum / total_weight, 2)


class SensorManager:
    """Handles sensor data reading and fusion for a room."""

    # Temperature-based window detection thresholds
    TEMP_DROP_THRESHOLD: float = 0.5  # °C drop in window to trigger detection
    TEMP_DROP_WINDOW: float = 300.0  # seconds (5 minutes)
    TEMP_DROP_CONFIRM: int = 2  # consecutive drops needed

    def __init__(self, coordinator: Any) -> None:
        """Initialize the sensor manager."""
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self._ema_value: float | None = None
        self._consecutive_spikes: int = 0
        # Temperature-based window detection state
        self._temp_drop_history: list[tuple[float, float]] = []  # (temp, timestamp)
        self._temp_drop_detected: bool = False
        self._temp_drop_count: int = 0

    def _debug(self, message: str, *args: Any) -> None:
        """Log sensor debug message using coordinator's logger."""
        if hasattr(self.coordinator, "debug"):
            self.coordinator.debug("sensors", message, *args)

    def get_fused_temperature(self) -> float | None:
        """Get the current room temperature from available sensors.

        Uses sensor fusion when both main and TRV sensors are available:
        the main sensor gets a fixed high weight while TRV weights are
        calculated dynamically based on their deviation from the main sensor.

        Falls back to TRV-only fusion when the main sensor is unavailable.
        Applies a dual-stage filter (spike rejection + EMA) on the result.
        """
        config = self.coordinator.room_config
        raw_temp: float | None = None

        main_temp = self._get_sensor_value(config.main_temp_sensor_id)

        if main_temp is not None:
            self._debug(
                "Temperature: MAIN SENSOR %s = %.2f",
                config.main_temp_sensor_id,
                main_temp,
            )

            # Build fusion list: main sensor + TRV sensors with dynamic weights
            readings: list[SensorReading] = [
                SensorReading(
                    entity_id=config.main_temp_sensor_id,
                    temperature=main_temp,
                    weight=10.0,
                )
            ]

            for trv_id in config.trv_entity_ids:
                state = self.hass.states.get(trv_id)
                if state:
                    try:
                        current = state.attributes.get("current_temperature")
                        if current is not None:
                            trv_temp = float(current)
                            weight = calculate_dynamic_trv_weight(main_temp, trv_temp)
                            readings.append(
                                SensorReading(
                                    entity_id=trv_id,
                                    temperature=trv_temp,
                                    weight=weight,
                                )
                            )
                            self._debug(
                                "TRV sensor %s = %.2f (dynamic weight: %.1f, diff: %.1f)",
                                trv_id,
                                trv_temp,
                                weight,
                                abs(main_temp - trv_temp),
                            )
                    except (ValueError, TypeError):
                        self._debug("TRV sensor %s: invalid value", trv_id)

            raw_temp = calculate_fused_temperature(readings)
            self._debug(
                "Temperature: FUSED from %d sensor(s) = %.2f",
                len(readings),
                raw_temp or 0,
            )
        else:
            # Fallback: TRV sensors only (no main sensor)
            trv_readings: list[SensorReading] = []
            for trv_id in config.trv_entity_ids:
                state = self.hass.states.get(trv_id)
                if state:
                    try:
                        current = state.attributes.get("current_temperature")
                        if current is not None:
                            reading = SensorReading(
                                entity_id=trv_id,
                                temperature=float(current),
                                weight=TRV_SENSOR_WEIGHT_DEFAULT,
                            )
                            trv_readings.append(reading)
                            self._debug(
                                "TRV sensor %s = %.2f (fallback weight: %.1f)",
                                trv_id,
                                float(current),
                                TRV_SENSOR_WEIGHT_DEFAULT,
                            )
                    except (ValueError, TypeError):
                        self._debug("TRV sensor %s: invalid value", trv_id)
                        continue

            if trv_readings:
                raw_temp = calculate_fused_temperature(trv_readings)
                self._debug(
                    "Temperature: FUSED from %d TRV(s) = %.2f (no main sensor)",
                    len(trv_readings),
                    raw_temp or 0,
                )

        if raw_temp is None:
            self._debug("Temperature: NO SENSORS AVAILABLE")
            return None

        # Apply dual-stage smoothing
        smoothed = self._apply_ema(raw_temp)
        self._debug(
            "Temperature: raw=%.2f -> smoothed=%.2f (alpha=%.2f)",
            raw_temp,
            smoothed,
            SENSOR_EMA_ALPHA,
        )
        return smoothed

    def _apply_ema(self, raw: float) -> float:
        """Apply dual-stage EMA filter with spike rejection.

        Stage 1 — Spike detection:
            If a reading deviates more than SPIKE_THRESHOLD from the current
            EMA, it is dampened with a very slow alpha.  If the same direction
            of spike persists for 3+ readings, accept it as a real shift.

        Stage 2 — Normal EMA:
            Standard exponential moving average for smooth tracking.

        On first reading the EMA seeds to the raw value immediately.
        """
        if self._ema_value is None:
            self._ema_value = raw
            self._consecutive_spikes = 0
            return round(self._ema_value, 2)

        deviation = abs(raw - self._ema_value)

        if deviation > SPIKE_THRESHOLD:
            self._consecutive_spikes += 1
            if self._consecutive_spikes >= 3:
                # Persistent deviation — accept as real (sensor moved/replaced)
                self._debug(
                    "Spike accepted after %d consecutive readings (dev=%.2f°C)",
                    self._consecutive_spikes,
                    deviation,
                )
                self._ema_value = raw
                self._consecutive_spikes = 0
            else:
                # Dampen the spike
                self._debug(
                    "Spike dampened (dev=%.2f°C, count=%d/3)",
                    deviation,
                    self._consecutive_spikes,
                )
                self._ema_value = (
                    SPIKE_DAMPENING_ALPHA * raw
                    + (1 - SPIKE_DAMPENING_ALPHA) * self._ema_value
                )
        else:
            self._consecutive_spikes = 0
            self._ema_value = (
                SENSOR_EMA_ALPHA * raw + (1 - SENSOR_EMA_ALPHA) * self._ema_value
            )

        return round(self._ema_value, 2)

    def get_outdoor_temperature(self) -> float | None:
        """Get current outdoor temperature."""
        config = self.coordinator.room_config

        # Try room-level outdoor sensor first
        outdoor_temp = self._get_sensor_value(config.outdoor_sensor_id)
        if outdoor_temp is not None:
            self._debug(
                "Outdoor: ROOM SENSOR %s = %.1f",
                config.outdoor_sensor_id,
                outdoor_temp,
            )
            return outdoor_temp

        # Fallback to hub's weather entity
        if self.coordinator.hub_coordinator:
            from ..const import CONF_WEATHER_ENTITY

            weather_entity = self.coordinator.hub_coordinator.config_data.get(
                CONF_WEATHER_ENTITY
            )
            if weather_entity:
                state = self.hass.states.get(weather_entity)
                if state:
                    try:
                        outdoor_temp = float(state.attributes.get("temperature"))
                        self._debug(
                            "Outdoor: WEATHER ENTITY %s = %.1f",
                            weather_entity,
                            outdoor_temp,
                        )
                        return outdoor_temp
                    except (ValueError, TypeError):
                        self._debug(
                            "Outdoor: WEATHER ENTITY %s - invalid value",
                            weather_entity,
                        )

        self._debug("Outdoor: NOT AVAILABLE")
        return None

    def get_humidity(self) -> float | None:
        """Get current room humidity."""
        config = self.coordinator.room_config
        humidity = self._get_sensor_value(config.humidity_sensor_id)

        if humidity is not None:
            self._debug(
                "Humidity: %s = %.1f%%",
                config.humidity_sensor_id,
                humidity,
            )

        return humidity

    def is_window_open(self) -> bool:
        """Check if any window is open (sensor or temperature-based detection)."""
        # 1. Check physical window sensors
        window_ids = self.coordinator.room_config.window_sensor_ids
        if window_ids:
            for entity_id in window_ids:
                state = self.hass.states.get(entity_id)
                if state and state.state == "on":
                    self._debug("Window: %s is OPEN (sensor)", entity_id)
                    return True

        # 2. Check temperature-based detection (works without window sensors)
        if self._temp_drop_detected:
            self._debug("Window: OPEN (temperature drop detected)")
            return True

        return False

    def update_temp_drop_detection(self, current_temp: float | None) -> None:
        """Track temperature drops to detect open windows without sensors.

        Call this every update cycle with the current fused temperature.
        A rapid drop (>TEMP_DROP_THRESHOLD in TEMP_DROP_WINDOW seconds)
        confirmed TEMP_DROP_CONFIRM times triggers the detection.  The
        detection clears when temperature stabilises or rises.
        """
        if current_temp is None:
            return

        now = _time.monotonic()
        self._temp_drop_history.append((current_temp, now))

        # Prune entries older than the detection window
        cutoff = now - self.TEMP_DROP_WINDOW
        self._temp_drop_history = [
            (t, ts) for t, ts in self._temp_drop_history if ts >= cutoff
        ]

        if len(self._temp_drop_history) < 2:
            return

        oldest_temp = self._temp_drop_history[0][0]
        drop = oldest_temp - current_temp

        if drop >= self.TEMP_DROP_THRESHOLD:
            self._temp_drop_count += 1
            if self._temp_drop_count >= self.TEMP_DROP_CONFIRM:
                if not self._temp_drop_detected:
                    self._debug(
                        "Window: Temp drop DETECTED (%.1f°C in %.0fs, count=%d)",
                        drop,
                        now - self._temp_drop_history[0][1],
                        self._temp_drop_count,
                    )
                self._temp_drop_detected = True
        else:
            # Temperature stabilised or rising — clear detection
            if self._temp_drop_detected:
                self._debug(
                    "Window: Temp drop CLEARED (temp stabilised at %.1f°C)",
                    current_temp,
                )
            self._temp_drop_detected = False
            self._temp_drop_count = 0

    def _get_sensor_value(self, entity_id: str | None) -> float | None:
        """Get numeric value from sensor."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None
