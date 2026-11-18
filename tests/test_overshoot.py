"""Unit tests for Overshoot Learning and Tracking (Anti-Hysterie / K-01)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

_TEST_ROOT = Path(__file__).resolve().parents[1]
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))


def _install_stubs():
    if "homeassistant" not in sys.modules:
        ha = types.ModuleType("homeassistant")
        ha.__path__ = []
        sys.modules["homeassistant"] = ha
    else:
        ha = sys.modules["homeassistant"]
        if not hasattr(ha, "__path__"):
            ha.__path__ = []

    if "homeassistant.core" not in sys.modules:
        ha_core = types.ModuleType("homeassistant.core")
        class HomeAssistant:
            pass
        ha_core.HomeAssistant = HomeAssistant
        sys.modules["homeassistant.core"] = ha_core
        ha.core = ha_core

    if "homeassistant.util" not in sys.modules:
        ha_util = types.ModuleType("homeassistant.util")
        ha_util.__path__ = []
        sys.modules["homeassistant.util"] = ha_util
        ha.util = ha_util
    else:
        ha_util = sys.modules["homeassistant.util"]
        if not hasattr(ha_util, "__path__"):
            ha_util.__path__ = []

    if "homeassistant.util.dt" not in sys.modules:
        ha_dt = types.ModuleType("homeassistant.util.dt")
        ha_dt.utcnow = lambda: datetime.now(timezone.utc)
        sys.modules["homeassistant.util.dt"] = ha_dt
        ha_util.dt = ha_dt

    cc_dir = _TEST_ROOT / "custom_components"
    tadiy_dir = cc_dir / "tadiy"
    core_dir = tadiy_dir / "core"

    if "custom_components" not in sys.modules:
        cc = types.ModuleType("custom_components")
        cc.__path__ = [str(cc_dir)]
        sys.modules["custom_components"] = cc

    if "custom_components.tadiy" not in sys.modules:
        tadiy = types.ModuleType("custom_components.tadiy")
        tadiy.__path__ = [str(tadiy_dir)]
        sys.modules["custom_components.tadiy"] = tadiy
        sys.modules["custom_components"].tadiy = tadiy

    if "custom_components.tadiy.core" not in sys.modules:
        core = types.ModuleType("custom_components.tadiy.core")
        core.__path__ = [str(core_dir)]
        sys.modules["custom_components.tadiy.core"] = core
        sys.modules["custom_components.tadiy"].core = core


_install_stubs()

from custom_components.tadiy.core.overshoot import (
    OvershootManager,
    OvershootModel,
    SETTLING_TIME,
    MIN_OVERSHOOT_THRESHOLD,
    MIN_SAMPLES_FOR_COMPENSATION,
)
import homeassistant.util.dt as dt_util


class TestOvershootLearning(unittest.TestCase):
    """Test overshoot learning model and manager."""

    def setUp(self):
        self.now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=timezone.utc)
        self.clock = {"now": self.now}
        self.patcher = patch.object(dt_util, "utcnow", side_effect=lambda: self.clock["now"])
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_overshoot_cycle_records_sample_after_settling_time(self):
        """Overshoot model waits for settling time after target is reached and records sample."""
        model = OvershootModel(room_name="Living Room")

        # 1. Start heating cycle: target 21.0, current 19.5
        model.start_heating_cycle(current_temp=19.5, target_temp=21.0)
        self.assertTrue(model._heating_cycle_active)

        # 2. Temperature approaches and reaches target at 10:10
        self.clock["now"] += timedelta(minutes=10)
        recorded = model.update_temperature(current_temp=21.0)
        self.assertFalse(recorded)
        self.assertIsNotNone(model._target_reached_time)

        # 3. Room continues warming to peak 21.8°C at 10:15 (during settling time)
        self.clock["now"] += timedelta(minutes=5)
        recorded = model.update_temperature(current_temp=21.8)
        self.assertFalse(recorded)
        self.assertEqual(model._peak_temp_after_target, 21.8)

        # 4. Settling time (10 min after reaching target) passes at 10:21
        self.clock["now"] += timedelta(minutes=6)
        recorded = model.update_temperature(current_temp=21.7)

        # Now sample must be recorded
        self.assertTrue(recorded)
        self.assertEqual(model.sample_count, 1)
        self.assertAlmostEqual(model.average_overshoot, 0.8, places=1)
        # Cycle ends itself
        self.assertFalse(model._heating_cycle_active)

    def test_compensation_applied_after_enough_samples(self):
        """Compensation is applied once min samples threshold is reached."""
        model = OvershootModel(room_name="Living Room")

        # Simulate 3 overshoot cycles with ~0.8°C overshoot each
        for i in range(MIN_SAMPLES_FOR_COMPENSATION):
            model.start_heating_cycle(19.0, 20.0)
            self.clock["now"] += timedelta(minutes=10)
            model.update_temperature(20.0)
            self.clock["now"] += timedelta(minutes=5)
            model.update_temperature(20.8)
            self.clock["now"] += SETTLING_TIME + timedelta(minutes=1)
            model.update_temperature(20.7)

        self.assertEqual(model.sample_count, 3)
        self.assertGreater(model.compensation, 0.0)
        # Target 21.0 compensated down by ~0.6°C
        compensated = model.get_compensated_target(21.0)
        self.assertLess(compensated, 21.0)
        self.assertAlmostEqual(compensated, 21.0 - model.compensation, places=2)


if __name__ == "__main__":
    unittest.main()
