"""TRV calibration and offset management for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Calibration limits
DEFAULT_TRV_CALIBRATION_MODE = "auto"  # auto | manual | disabled
DEFAULT_TRV_MULTIPLIER = 1.0
MIN_TRV_MULTIPLIER = 0.5
MAX_TRV_MULTIPLIER = 2.0
DEFAULT_TRV_OFFSET = 0.0  # Only used in manual mode
MIN_TRV_OFFSET = -10.0
MAX_TRV_OFFSET = 10.0

# Auto-calibration smoothing
DAMPENING = 0.1  # 10% weight to new measurement (exponential moving average)


@dataclass
class TRVCalibration:
    """Calibration data for a single TRV."""

    entity_id: str
    mode: str = "auto"  # auto | manual | disabled
    multiplier: float = 1.0  # Multiplier for auto mode (room_temp / trv_temp)
    offset: float = 0.0  # °C offset for manual mode
    last_calibrated: datetime | None = None
    last_room_temp: float | None = None  # For auto-calibration tracking
    last_trv_temp: float | None = None
    last_calibrated_target: float | None = None  # Last returned calibrated target

    def apply_calibration(
        self,
        target_temp: float,
        room_temp: float | None = None,
        trv_temp: float | None = None,
    ) -> float:
        """
        Apply calibration to target temperature.

        Args:
            target_temp: Desired room temperature
            room_temp: Current room temperature (for auto mode)
            trv_temp: Current TRV sensor reading (for auto mode)

        Returns:
            Calibrated target for TRV
        """
        # If disabled, just pass through
        if self.mode == "disabled":
            return round(target_temp, 1)

        # If manual, apply fixed offset
        if self.mode == "manual":
            calibrated = target_temp + self.offset
            return round(calibrated, 1)

        # Auto mode: Determine difference between TRV internal and Room Actual
        # Formula: Target_TRV = Target_Room + (TRV_Temp - Room_Temp)
        # Example: Target 21, TRV sees 25, Room is 19.
        # Difference = 25 - 19 = 6 deg.
        # We need the TRV to "feel" 25 but work towards 21. TRV Logic thinks 21 is attained when it feels 21.
        # It feels 25. So we must ask for 21 + 6 = 27 (roughly).
        # Actually: If we want Room to contain 21 heat, and TRV is hot (25), we need to set TRV to:
        # Target + (TRV - Room).
        # Setpoint = 21 + (25 - 19) = 27.

        if room_temp is not None and trv_temp is not None:
            diff = trv_temp - room_temp

            # Update internal offset for tracking
            self.offset = diff

            # Apply dynamic offset
            calibrated = target_temp + diff
            return round(calibrated, 1)

        return round(target_temp, 1)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "entity_id": self.entity_id,
            "mode": self.mode,
            "multiplier": self.multiplier,
            "offset": self.offset,
            "last_calibrated": (
                self.last_calibrated.isoformat() if self.last_calibrated else None
            ),
            "last_room_temp": self.last_room_temp,
            "last_trv_temp": self.last_trv_temp,
            "last_calibrated_target": self.last_calibrated_target,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TRVCalibration:
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            mode=data.get("mode", DEFAULT_TRV_CALIBRATION_MODE),
            multiplier=data.get("multiplier", DEFAULT_TRV_MULTIPLIER),
            offset=data.get("offset", DEFAULT_TRV_OFFSET),
            last_calibrated=(
                datetime.fromisoformat(data["last_calibrated"])
                if data.get("last_calibrated")
                else None
            ),
            last_room_temp=data.get("last_room_temp"),
            last_trv_temp=data.get("last_trv_temp"),
            last_calibrated_target=data.get("last_calibrated_target"),
        )


class CalibrationManager:
    """Manage TRV calibrations for all rooms."""

    def __init__(self, debug_callback=None) -> None:
        """Initialize calibration manager."""
        self._calibrations: dict[str, TRVCalibration] = {}
        self._debug_fn = debug_callback

    def _debug(self, message: str, *args: Any) -> None:
        """Log via TaDIY debug system if available, else fallback to _LOGGER."""
        if self._debug_fn:
            self._debug_fn("calibration", message, args)
        else:
            _LOGGER.debug(message, *args)

    def set_mode(self, entity_id: str, mode: str) -> None:
        """
        Set calibration mode for a TRV.

        Args:
            entity_id: TRV entity ID
            mode: Calibration mode (auto | manual | disabled)
        """
        if mode not in ("auto", "manual", "disabled"):
            raise ValueError(f"Invalid calibration mode: {mode}")

        if entity_id not in self._calibrations:
            self._calibrations[entity_id] = TRVCalibration(entity_id=entity_id)

        self._calibrations[entity_id].mode = mode
        self._calibrations[entity_id].last_calibrated = dt_util.utcnow()
        self._debug("TRV %s: Set calibration mode to %s", entity_id, mode)

    def set_manual_offset(self, entity_id: str, offset: float) -> None:
        """
        Manually set calibration offset for a TRV.

        Args:
            entity_id: TRV entity ID
            offset: Offset in °C

        Raises:
            ValueError: If offset is out of range
        """
        if not MIN_TRV_OFFSET <= offset <= MAX_TRV_OFFSET:
            raise ValueError(f"Offset {offset} out of range")

        if entity_id not in self._calibrations:
            self._calibrations[entity_id] = TRVCalibration(entity_id=entity_id)

        self._calibrations[entity_id].offset = offset
        self._calibrations[entity_id].mode = "manual"  # Force manual mode
        self._calibrations[entity_id].last_calibrated = dt_util.utcnow()
        self._debug("TRV %s: Set manual offset to %.1f°C", entity_id, offset)

    def set_multiplier(self, entity_id: str, multiplier: float) -> None:
        """
        Set auto-calibration multiplier for a TRV.

        Args:
            entity_id: TRV entity ID
            multiplier: Calibration multiplier

        Raises:
            ValueError: If multiplier is out of range
        """
        if not MIN_TRV_MULTIPLIER <= multiplier <= MAX_TRV_MULTIPLIER:
            raise ValueError(f"Multiplier {multiplier} out of range")

        if entity_id not in self._calibrations:
            self._calibrations[entity_id] = TRVCalibration(entity_id=entity_id)

        self._calibrations[entity_id].multiplier = multiplier
        self._calibrations[entity_id].last_calibrated = dt_util.utcnow()
        self._debug("TRV %s: Set multiplier to %.3f", entity_id, multiplier)

    def get_calibrated_target(
        self,
        entity_id: str,
        target_temp: float,
        room_temp: float | None = None,
        trv_temp: float | None = None,
        max_temp: float = 30.0,
        min_step: float = 0.5,
    ) -> float:
        """Get calibrated target for a TRV using EMA-smoothed offset.

        The TRV sensor is typically warmer than the room sensor (closer to
        radiator).  We compensate with: calibrated = target + smoothed_offset.

        The offset is EMA-smoothed via update_calibration() to prevent
        oscillation from independent sensor fluctuations.

        A minimum change threshold (min_step) suppresses commands when the
        calibrated target has not changed significantly.

        Args:
            entity_id: TRV entity ID
            target_temp: Desired room temperature
            room_temp: Current room temperature from external sensor
            trv_temp: Current TRV's internal sensor reading
            max_temp: Maximum allowed temperature (clamp limit)
            min_step: Minimum change to return a new value (from target_temp_step)

        Returns:
            Calibrated target temperature for the TRV
        """
        if room_temp is not None and trv_temp is not None:
            # 1. Update EMA-smoothed offset
            self.update_calibration(entity_id, trv_temp, room_temp)

            cal = self._calibrations[entity_id]

            # 2. Calculate calibrated target using smoothed offset
            calibrated = min(target_temp + cal.offset, max_temp)
            calibrated = round(calibrated, 1)

            self._debug(
                "TRV %s: target=%.1f room=%.1f trv=%.1f "
                "smoothed_offset=%+.1f -> calibrated=%.1f",
                entity_id,
                target_temp,
                room_temp,
                trv_temp,
                cal.offset,
                calibrated,
            )

            # 3. Suppress if change is below minimum step
            if (
                cal.last_calibrated_target is not None
                and abs(calibrated - cal.last_calibrated_target) < min_step
            ):
                self._debug(
                    "TRV %s: Suppressed (delta=%.2f < step=%.1f), keeping %.1f",
                    entity_id,
                    abs(calibrated - cal.last_calibrated_target),
                    min_step,
                    cal.last_calibrated_target,
                )
                return cal.last_calibrated_target

            cal.last_calibrated_target = calibrated
            return calibrated

        return round(target_temp, 1)

    def update_calibration(
        self, entity_id: str, trv_temp: float, room_temp: float
    ) -> None:
        """
        Update automatic calibration offset based on sensor discrepancy.

        Offset Logic:
        - diff = trv_temp - room_temp
        - Apply dampening (smoothing)
        - Save new offset

        Args:
            entity_id: TRV entity ID
            trv_temp: Current TRV sensor reading
            room_temp: Current room temperature
        """
        if entity_id not in self._calibrations:
            self._calibrations[entity_id] = TRVCalibration(
                entity_id=entity_id, mode="auto"
            )

        cal = self._calibrations[entity_id]

        # Only update if in auto mode
        if cal.mode != "auto":
            return

        # Validate inputs
        if trv_temp <= 0 or room_temp <= 0:
            return

        # Calculate current difference
        raw_diff = trv_temp - room_temp

        # Dampening (smoothing)
        # If offset is 0.0 (initial), set directly
        if cal.offset == 0.0:
            cal.offset = raw_diff
        else:
            # Smooth usage: 80% old value, 20% new value
            cal.offset = (1 - DAMPENING) * cal.offset + DAMPENING * raw_diff

        # Clamp check if needed (e.g. max +/- 15 degrees)
        # Using 15.0 as a safe upper bound for offset
        cal.offset = max(min(cal.offset, 15.0), -15.0)

        # Update tracking
        cal.last_room_temp = room_temp
        cal.last_trv_temp = trv_temp
        cal.last_calibrated = dt_util.utcnow()

        self._debug(
            "TRV %s auto-calibration: room=%.1f trv=%.1f "
            "raw_diff=%+.1f smoothed_offset=%+.1f",
            entity_id,
            room_temp,
            trv_temp,
            raw_diff,
            cal.offset,
        )

    def get_calibration_info(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get calibration information for a TRV.

        Args:
            entity_id: TRV entity ID

        Returns:
            Calibration info dict or None if not calibrated
        """
        if entity_id not in self._calibrations:
            return None

        cal = self._calibrations[entity_id]
        return {
            "mode": cal.mode,
            "multiplier": cal.multiplier,
            "offset": cal.offset,
            "last_calibrated": cal.last_calibrated,
            "last_room_temp": cal.last_room_temp,
            "last_trv_temp": cal.last_trv_temp,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert all calibrations to dictionary for storage."""
        return {
            entity_id: cal.to_dict() for entity_id, cal in self._calibrations.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], debug_callback=None) -> CalibrationManager:
        """Create calibration manager from dictionary."""
        manager = cls(debug_callback=debug_callback)
        for entity_id, cal_data in data.items():
            manager._calibrations[entity_id] = TRVCalibration.from_dict(cal_data)
        return manager
