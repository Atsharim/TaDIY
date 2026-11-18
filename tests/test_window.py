"""Unit tests for custom_components.tadiy.core.window.

Stubs the homeassistant modules in sys.modules before importing the package,
so that custom_components.tadiy.core.window is importable without homeassistant
being installed and without executing tadiy/__init__.py or core/__init__.py.
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_TEST_ROOT = Path(__file__).resolve().parents[1]
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))


def _install_homeassistant_stub() -> None:
    """Stub homeassistant, homeassistant.util and homeassistant.util.dt."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    ha_util = types.ModuleType("homeassistant.util")
    ha_dt = types.ModuleType("homeassistant.util.dt")

    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def now() -> datetime:
        return datetime.now(timezone.utc)

    ha_dt.utcnow = utcnow  # type: ignore[attr-defined]
    ha_dt.now = now  # type: ignore[attr-defined]

    ha.util = ha_util  # type: ignore[attr-defined]
    ha_util.dt = ha_dt  # type: ignore[attr-defined]

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.dt"] = ha_dt


def _install_custom_components_stubs() -> None:
    """Create empty package modules pointing at the real directories."""
    cc_dir = _TEST_ROOT / "custom_components"
    tadiy_dir = cc_dir / "tadiy"
    core_dir = tadiy_dir / "core"

    if "custom_components" not in sys.modules:
        cc = types.ModuleType("custom_components")
        cc.__path__ = [str(cc_dir)]  # type: ignore[attr-defined]
        sys.modules["custom_components"] = cc

    if "custom_components.tadiy" not in sys.modules:
        tadiy = types.ModuleType("custom_components.tadiy")
        tadiy.__path__ = [str(tadiy_dir)]  # type: ignore[attr-defined]
        sys.modules["custom_components.tadiy"] = tadiy
        cc = sys.modules["custom_components"]
        cc.tadiy = tadiy  # type: ignore[attr-defined]

    if "custom_components.tadiy.core" not in sys.modules:
        core = types.ModuleType("custom_components.tadiy.core")
        core.__path__ = [str(core_dir)]  # type: ignore[attr-defined]
        sys.modules["custom_components.tadiy.core"] = core
        tadiy = sys.modules["custom_components.tadiy"]
        tadiy.core = core  # type: ignore[attr-defined]


def _install_and_import():
    _install_homeassistant_stub()
    _install_custom_components_stubs()
    importlib.invalidate_caches()
    window_mod = importlib.import_module("custom_components.tadiy.core.window")
    return window_mod


window_mod = _install_and_import()
WindowDetector = window_mod.WindowDetector
WindowState = window_mod.WindowState


class WindowTimeoutTestCase(unittest.TestCase):
    """Shared fake-clock setup for window tests."""

    OPEN_TIMEOUT = 60
    CLOSE_TIMEOUT = 90
    START = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def setUp(self) -> None:
        self.clock = {"now": self.START}
        for name in ("utcnow", "now"):
            patcher = patch.object(
                window_mod.dt_util,
                name,
                side_effect=lambda: self.clock["now"],
                create=True,
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        self.detector = WindowDetector(
            open_timeout_seconds=self.OPEN_TIMEOUT,
            close_timeout_seconds=self.CLOSE_TIMEOUT,
        )

    def advance(self, seconds: float) -> None:
        self.clock["now"] = self.clock["now"] + timedelta(seconds=seconds)

    def closed(self) -> WindowState:
        return WindowState(is_open=False, reason="sensor")

    def opened(self) -> WindowState:
        return WindowState(is_open=True, reason="sensor")


class TestOpenTimeout(WindowTimeoutTestCase):
    def test_open_before_timeout_keeps_heating(self) -> None:
        self.detector.update(self.closed())
        state = self.detector.update(self.opened())
        self.assertIsInstance(state, WindowState)
        self.assertFalse(state.heating_should_stop)
        self.assertTrue(state.timeout_active)
        self.assertEqual(state.timeout_ends_at, self.START + timedelta(seconds=60))

    def test_open_after_timeout_stops_heating(self) -> None:
        self.detector.update(self.closed())
        self.detector.update(self.opened())
        self.advance(self.OPEN_TIMEOUT + 1)
        state = self.detector.update(self.opened())
        self.assertTrue(state.heating_should_stop)
        self.assertTrue(state.is_open)
        self.assertFalse(state.timeout_ends_at)


class TestRepeatedUpdates(WindowTimeoutTestCase):
    def test_same_raw_state_does_not_reset_timer(self) -> None:
        self.detector.update(self.closed())
        self.detector.update(self.opened())
        first_end = self.detector.update(self.opened()).timeout_ends_at
        self.advance(30)
        state = self.detector.update(self.opened())
        self.assertEqual(state.timeout_ends_at, first_end)
        self.assertFalse(state.heating_should_stop)
        self.advance(31)
        state = self.detector.update(self.opened())
        self.assertTrue(state.heating_should_stop)
        self.assertFalse(state.timeout_ends_at)


class TestCloseWithinGrace(WindowTimeoutTestCase):
    def test_close_before_open_timeout_cancels_grace(self) -> None:
        self.detector.update(self.closed())
        grace = self.detector.update(self.opened())
        self.assertTrue(grace.timeout_active)
        self.advance(20)
        state = self.detector.update(self.closed())
        self.assertFalse(state.heating_should_stop)
        self.assertFalse(state.timeout_active)
        self.assertIsNone(state.timeout_ends_at)


class TestUpdateTimeouts(WindowTimeoutTestCase):
    def test_new_values_applied(self) -> None:
        detector = WindowDetector(
            open_timeout_seconds=3600, close_timeout_seconds=3600
        )
        detector.update(self.closed())
        detector.update_timeouts(30, 120)
        self.assertEqual(detector._open_timeout, timedelta(seconds=30))
        self.assertEqual(detector._close_timeout, timedelta(seconds=120))
        state = detector.update(self.opened())
        self.assertFalse(state.heating_should_stop)
        self.advance(35)
        state = detector.update(self.opened())
        self.assertTrue(state.heating_should_stop)


class TestWindowState(WindowTimeoutTestCase):
    def test_defaults_and_to_dict(self) -> None:
        state = WindowState(is_open=True)
        self.assertEqual(state.reason, "unknown")
        self.assertFalse(state.heating_should_stop)
        self.assertFalse(state.timeout_active)
        self.assertIsNone(state.timeout_ends_at)
        data = state.to_dict()
        self.assertTrue(data["is_open"])
        self.assertEqual(data["reason"], "unknown")
        self.assertFalse(data["heating_should_stop"])
        self.assertFalse(data["timeout_active"])
        self.assertIsNone(data["timeout_ends_at"])


if __name__ == "__main__":
    unittest.main()
