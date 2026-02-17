"""Window detection logic for TaDIY."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class WindowState:
    """Represents detected window state."""
    is_open: bool
    last_change: datetime | None = None
    reason: str | None = None
