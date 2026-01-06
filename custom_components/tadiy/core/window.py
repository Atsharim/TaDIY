"""Window detection logic for TaDIY."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass(slots=True)
class WindowState:
    """Represents detected window state with timeout handling."""
    
    is_open: bool
    last_change: datetime | None = None
    reason: str | None = None
    timeout_active: bool = False
    heating_should_stop: bool = False


class WindowDetector:
    """Detects window state with configurable timeouts."""

    def __init__(
        self,
        open_timeout_seconds: int = 300,
        close_timeout_seconds: int = 900,
    ) -> None:
        """Initialize window detector.
        
        Args:
            open_timeout_seconds: Time window must be open before heating stops
            close_timeout_seconds: Time window must be closed before heating resumes
        """
        self.open_timeout = timedelta(seconds=open_timeout_seconds)
        self.close_timeout = timedelta(seconds=close_timeout_seconds)
        self._last_state: WindowState | None = None
        self._open_since: datetime | None = None
        self._closed_since: datetime | None = None

    def update(
        self,
        current_state: WindowState,
        now: datetime | None = None,
    ) -> WindowState:
        """Update window state with timeout logic.
        
        Args:
            current_state: Current raw window state from sensors
            now: Current time (for testing, defaults to utcnow)
            
        Returns:
            WindowState with timeout logic applied
        """
        if now is None:
            now = dt_util.utcnow()

        # No sensors available
        if current_state.reason == "no_sensors":
            return WindowState(
                is_open=False,
                reason="no_sensors",
                heating_should_stop=False,
            )

        # Detect state change
        if self._last_state is None or self._last_state.is_open != current_state.is_open:
            if current_state.is_open:
                self._open_since = now
                self._closed_since = None
            else:
                self._closed_since = now
                self._open_since = None

        self._last_state = current_state

        # WINDOW OPEN: Check timeout
        if current_state.is_open:
            time_open = now - self._open_since if self._open_since else timedelta(0)
            
            if time_open >= self.open_timeout:
                return WindowState(
                    is_open=True,
                    last_change=self._open_since,
                    reason="open_timeout_reached",
                    timeout_active=True,
                    heating_should_stop=True,
                )
            else:
                return WindowState(
                    is_open=True,
                    last_change=self._open_since,
                    reason="open_but_within_timeout",
                    timeout_active=False,
                    heating_should_stop=False,
                )

        # WINDOW CLOSED: Check timeout
        else:
            time_closed = now - self._closed_since if self._closed_since else timedelta(0)
            
            # If previously open for long, delay before resume
            if time_closed < self.close_timeout:
                return WindowState(
                    is_open=False,
                    last_change=self._closed_since,
                    reason="closed_but_cooldown_active",
                    timeout_active=True,
                    heating_should_stop=True,  # Don't heat yet
                )
            else:
                return WindowState(
                    is_open=False,
                    last_change=self._closed_since,
                    reason="closed_ready_to_heat",
                    timeout_active=False,
                    heating_should_stop=False,
                )

    def reset(self) -> None:
        """Reset detector state (e.g., after config change)."""
        self._last_state = None
        self._open_since = None
        self._closed_since = None


def detect_window_by_temperature_drop(
    current_temp: float,
    previous_temp: float,
    time_delta_minutes: float,
    threshold_per_minute: float = 0.1,
) -> bool:
    """Detect window opening by rapid temperature drop.
    
    Alternative detection method when no sensors available.
    
    Args:
        current_temp: Current temperature
        previous_temp: Previous temperature
        time_delta_minutes: Time between measurements
        threshold_per_minute: °C drop per minute to trigger detection
        
    Returns:
        True if rapid drop detected (likely window open)
    """
    if time_delta_minutes <= 0:
        return False

    temp_drop = previous_temp - current_temp
    drop_per_minute = temp_drop / time_delta_minutes

    return drop_per_minute >= threshold_per_minute
