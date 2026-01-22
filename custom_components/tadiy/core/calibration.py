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
DAMPENING = 0.2  # 20% weight to new measurement (exponential moving average)


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
        if self.mode == "disabled":
            return round(target_temp, 1)

        if self.mode == "manual":
            # Manual mode: apply fixed offset
            calibrated = target_temp + self.offset
            return round(calibrated, 1)

        if self.mode == "auto":
            # Auto mode: apply multiplier based on sensor discrepancy
            if room_temp is not None and trv_temp is not None and trv_temp > 0:
                # Calculate correction using multiplier
                # If TRV reads higher than room (near radiator): multiplier < 1.0
                # If TRV reads lower than room: multiplier > 1.0
                # Correction = target * multiplier
                calibrated = target_temp * self.multiplier
                return round(calibrated, 1)
            else:
                # Fallback: no calibration if sensors unavailable
                return round(target_temp, 1)

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
        )


class CalibrationManager:
    """Manage TRV calibrations for all rooms."""

    def __init__(self) -> None:
        """Initialize calibration manager."""
        self._calibrations: dict[str, TRVCalibration] = {}

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
        _LOGGER.info("TRV %s: Set calibration mode to %s", entity_id, mode)

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
        _LOGGER.info("TRV %s: Set manual offset to %.1f°C", entity_id, offset)

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
        _LOGGER.info("TRV %s: Set multiplier to %.3f", entity_id, multiplier)

    def get_calibrated_target(
        self,
        entity_id: str,
        target_temp: float,
        room_temp: float | None = None,
        trv_temp: float | None = None,
    ) -> float:
        """
        Get calibrated target for a TRV.

        Args:
            entity_id: TRV entity ID
            target_temp: Desired room temperature
            room_temp: Current room temperature (for auto mode)
            trv_temp: Current TRV sensor reading (for auto mode)

        Returns:
            Calibrated target temperature
        """
        if entity_id in self._calibrations:
            return self._calibrations[entity_id].apply_calibration(
                target_temp, room_temp, trv_temp
            )
        return target_temp

    def update_auto_calibration(
        self,
        entity_id: str,
        trv_temp: float,
        room_temp: float,
    ) -> None:
        """
        Update automatic calibration multiplier based on sensor discrepancy.

        Multiplier Logic:
        - multiplier = room_temp / trv_temp
        - If TRV reads 22°C but room is 20°C: multiplier = 20/22 = 0.91
        - If TRV reads 18°C but room is 20°C: multiplier = 20/18 = 1.11
        - Apply dampening to prevent overcorrection

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

        # Calculate raw multiplier
        raw_multiplier = room_temp / trv_temp

        # Apply exponential moving average for smoothing (dampening)
        if cal.multiplier == 1.0:
            # First calibration
            cal.multiplier = raw_multiplier
        else:
            # Smooth update
            cal.multiplier = (1 - DAMPENING) * cal.multiplier + DAMPENING * raw_multiplier

        # Clamp to limits
        cal.multiplier = max(
            MIN_TRV_MULTIPLIER, min(MAX_TRV_MULTIPLIER, cal.multiplier)
        )

        # Update tracking
        cal.last_room_temp = room_temp
        cal.last_trv_temp = trv_temp
        cal.last_calibrated = dt_util.utcnow()

        _LOGGER.debug(
            "TRV %s auto-calibration: room=%.1f°C, trv=%.1f°C, "
            "raw_multiplier=%.3f, smoothed_multiplier=%.3f",
            entity_id,
            room_temp,
            trv_temp,
            raw_multiplier,
            cal.multiplier,
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
    def from_dict(cls, data: dict[str, Any]) -> CalibrationManager:
        """Create calibration manager from dictionary."""
        manager = cls()
        for entity_id, cal_data in data.items():
            manager._calibrations[entity_id] = TRVCalibration.from_dict(cal_data)
        return manager
