"""Window detection logic for TaDIY."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import (
    DEFAULT_WINDOW_CLOSE_TIMEOUT,
    DEFAULT_WINDOW_OPEN_TIMEOUT,
    MIN_WINDOW_TIMEOUT,
    MAX_WINDOW_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WindowState:
    """State of a window with timeout logic."""

    is_open: bool
    reason: str = "unknown"
    last_change: datetime | None = None
    heating_should_stop: bool = False
    timeout_active: bool = False
    timeout_ends_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_open": self.is_open,
            "reason": self.reason,
            "last_change": self.last_change.isoformat() if self.last_change else None,
            "heating_should_stop": self.heating_should_stop,
            "timeout_active": self.timeout_active,
            "timeout_ends_at": (
                self.timeout_ends_at.isoformat() if self.timeout_ends_at else None
            ),
        }


class WindowDetector:
    """Detects window open/close events with configurable timeouts."""

    def __init__(
        self,
        open_timeout_seconds: int = DEFAULT_WINDOW_OPEN_TIMEOUT,
        close_timeout_seconds: int = DEFAULT_WINDOW_CLOSE_TIMEOUT,
    ) -> None:
        """Initialize window detector."""
        if not MIN_WINDOW_TIMEOUT <= open_timeout_seconds <= MAX_WINDOW_TIMEOUT:
            raise ValueError(
                f"open_timeout_seconds must be between {MIN_WINDOW_TIMEOUT} "
                f"and {MAX_WINDOW_TIMEOUT}"
            )
        if not MIN_WINDOW_TIMEOUT <= close_timeout_seconds <= MAX_WINDOW_TIMEOUT:
            raise ValueError(
                f"close_timeout_seconds must be between {MIN_WINDOW_TIMEOUT} "
                f"and {MAX_WINDOW_TIMEOUT}"
            )

        self._open_timeout = timedelta(seconds=open_timeout_seconds)
        self._close_timeout = timedelta(seconds=close_timeout_seconds)
        self._current_state: WindowState | None = None
        self._state_changed_at: datetime | None = None
        self._timeout_started_at: datetime | None = None

        _LOGGER.debug(
            "WindowDetector initialized: open_timeout=%ds, close_timeout=%ds",
            open_timeout_seconds,
            close_timeout_seconds,
        )

    def update(self, raw_state: WindowState) -> WindowState:
        """Update window state with timeout logic."""
        now = dt_util.utcnow()

        if self._current_state is None:
            self._current_state = WindowState(
                is_open=raw_state.is_open,
                reason=raw_state.reason,
                last_change=now,
                heating_should_stop=raw_state.is_open,
                timeout_active=False,
            )
            self._state_changed_at = now
            _LOGGER.info(
                "Window state initialized: %s (%s)",
                "OPEN" if raw_state.is_open else "CLOSED",
                raw_state.reason,
            )
            return self._current_state

        if raw_state.is_open != self._current_state.is_open:
            if self._state_changed_at is None or (
                now - self._state_changed_at
            ) > timedelta(seconds=5):
                _LOGGER.info(
                    "Window state change detected: %s -> %s (%s)",
                    "OPEN" if self._current_state.is_open else "CLOSED",
                    "OPEN" if raw_state.is_open else "CLOSED",
                    raw_state.reason,
                )
                self._state_changed_at = now
                self._timeout_started_at = now

        if self._state_changed_at is None:
            self._state_changed_at = now

        time_since_change = now - self._state_changed_at

        if raw_state.is_open and not self._current_state.is_open:
            if time_since_change >= self._open_timeout:
                self._current_state = WindowState(
                    is_open=True,
                    reason=raw_state.reason,
                    last_change=now,
                    heating_should_stop=True,
                    timeout_active=True,
                    timeout_ends_at=None,
                )
                _LOGGER.info(
                    "Window OPEN timeout exceeded (%ds) - Heating STOPPED",
                    self._open_timeout.total_seconds(),
                )
            else:
                remaining = (self._open_timeout - time_since_change).total_seconds()
                _LOGGER.debug("Window opening detected, timeout in %.0fs", remaining)
                self._current_state.timeout_active = False
                self._current_state.heating_should_stop = False

        elif not raw_state.is_open and self._current_state.is_open:
            if time_since_change >= self._close_timeout:
                self._current_state = WindowState(
                    is_open=False,
                    reason=raw_state.reason,
                    last_change=now,
                    heating_should_stop=False,
                    timeout_active=False,
                )
                _LOGGER.info(
                    "Window CLOSED timeout exceeded (%ds) - Heating RESUMED",
                    self._close_timeout.total_seconds(),
                )
                self._timeout_started_at = None
            else:
                remaining = (self._close_timeout - time_since_change).total_seconds()
                _LOGGER.debug(
                    "Window closing detected, cooldown remaining: %.0fs", remaining
                )
                timeout_end = self._state_changed_at + self._close_timeout
                self._current_state.timeout_active = True
                self._current_state.heating_should_stop = True
                self._current_state.timeout_ends_at = timeout_end

        elif self._current_state.timeout_active:
            if self._current_state.is_open:
                self._current_state.heating_should_stop = True
            else:
                if (
                    self._timeout_started_at
                    and (now - self._timeout_started_at) >= self._close_timeout
                ):
                    self._current_state.timeout_active = False
                    self._current_state.heating_should_stop = False
                    self._current_state.timeout_ends_at = None
                    self._timeout_started_at = None
                    _LOGGER.info("Window close cooldown complete - Heating can resume")
                else:
                    timeout_end = self._state_changed_at + self._close_timeout
                    self._current_state.timeout_ends_at = timeout_end

        return self._current_state

    def reset(self) -> None:
        """Reset detector state."""
        self._current_state = None
        self._state_changed_at = None
        self._timeout_started_at = None
        _LOGGER.info("Window detector reset")
