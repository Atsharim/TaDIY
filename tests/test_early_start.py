"""Unit tests for HeatUpModel and EarlyStartCalculator (K-09)."""

from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path
import sys
import types
import unittest

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

from custom_components.tadiy.core.early_start import EarlyStartCalculator, HeatUpModel
from custom_components.tadiy.const import (
    DEFAULT_HEATING_RATE,
    MIN_HEATING_RATE,
    MAX_HEATING_RATE,
)


class TestHeatUpModelAPI(unittest.TestCase):
    """Test HeatUpModel clean API for setting manual rates (K-09)."""

    def test_set_manual_rate_resets_confidence(self):
        """Setting manual rate establishes a clean baseline with sample_count=1 (not artificial high confidence)."""
        model = HeatUpModel(room_name="Office")
        # Simulate having accumulated 50 samples previously
        model.sample_count = 50
        model._running_sum = 50 * 1.2
        model.degrees_per_hour = 1.2
        self.assertEqual(model.get_confidence(), 1.0)

        # Set manual rate to 2.0 °C/h
        model.set_manual_rate(2.0, reset_samples=True)

        self.assertEqual(model.get_heating_rate(), 2.0)
        self.assertEqual(model.sample_count, 1)
        self.assertEqual(model._running_sum, 2.0)
        self.assertAlmostEqual(model.get_confidence(), 1 / 50)

    def test_set_manual_rate_validation(self):
        """Out of bounds rates raise ValueError."""
        model = HeatUpModel(room_name="Office")
        with self.assertRaises(ValueError):
            model.set_manual_rate(MIN_HEATING_RATE - 0.05)
        with self.assertRaises(ValueError):
            model.set_manual_rate(MAX_HEATING_RATE + 1.0)

    def test_reset_model(self):
        """Reset clears model to default rate and zero samples."""
        model = HeatUpModel(room_name="Office")
        model.set_manual_rate(2.5)
        self.assertEqual(model.sample_count, 1)

        model.reset()
        self.assertEqual(model.get_heating_rate(), DEFAULT_HEATING_RATE)
        self.assertEqual(model.sample_count, 0)
        self.assertEqual(model._running_sum, 0.0)

    def test_early_start_calculator_preheat_minutes(self):
        """EarlyStartCalculator determines preheat start time based on heating rate."""
        model = HeatUpModel(room_name="Office")
        model.sample_count = 50  # High confidence
        model.degrees_per_hour = 2.0  # 2.0 °C per hour

        calc = EarlyStartCalculator(model)
        target_time = datetime(2026, 11, 12, 8, 0, 0, tzinfo=timezone.utc)

        # Need 2.0 °C increase (18°C -> 20°C) at 2.0 °C/h -> 1 hour needed -> start at 7:00
        start_time = calc.calculate_start_time(
            current_temp=18.0,
            target_temp=20.0,
            target_time=target_time,
        )
        self.assertEqual(start_time, datetime(2026, 11, 12, 7, 0, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
