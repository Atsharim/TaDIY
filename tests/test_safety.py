"""Unit tests for SafetyManager failure and safety monitoring (K-13)."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

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
        def utcnow() -> datetime:
            return datetime.now(timezone.utc)
        def now() -> datetime:
            return datetime.now(timezone.utc)
        ha_dt.utcnow = utcnow
        ha_dt.now = now
        ha_dt.parse_datetime = lambda s: datetime.fromisoformat(s) if s else None
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
importlib.invalidate_caches()

safety_mod = importlib.import_module("custom_components.tadiy.core.safety")
from custom_components.tadiy.core.safety import (
    SafetyManager,
    OVERHEAT_TEMP,
    FROST_FLOOR_TEMP,
    VALVE_STUCK_TIMEOUT,
)

_B0 = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)


class TestSafetyManager(unittest.TestCase):
    """Test suite for SafetyManager failure detection (K-13)."""

    def setUp(self) -> None:
        self.clock = {"now": _B0}
        for name in ("utcnow", "now"):
            patcher = patch.object(
                safety_mod.dt_util,
                name,
                side_effect=lambda: self.clock["now"],
                create=True,
            )
            patcher.start()
            self.addCleanup(patcher.stop)

        self.mgr = SafetyManager("Wohnzimmer")

    def test_normal_operation_no_alerts(self):
        """Room within normal target bounds has no alerts."""
        state = self.mgr.check_safety(
            current_temp=20.0,
            target_temp=20.0,
            heating_active=False,
        )
        self.assertFalse(state.any_alert)
        self.assertIsNone(state.active_problem_type)

    def test_valve_stuck_open_detection(self):
        """Detect stuck open valve when room continues heating above setpoint."""
        # Target 18.0, room at 20.0 (+2.0°C). Heating is inactive.
        self.mgr.check_safety(current_temp=20.0, target_temp=18.0, heating_active=False)
        self.assertFalse(self.mgr.state.valve_stuck_open)

        # 10 minutes later: room at 20.2°C (still within timeout)
        self.clock["now"] = _B0 + timedelta(minutes=10)
        self.mgr.check_safety(current_temp=20.2, target_temp=18.0, heating_active=False)
        self.assertFalse(self.mgr.state.valve_stuck_open)

        # 35 minutes later (> 30 min timeout): room at 20.5°C (not cooled down)
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(current_temp=20.5, target_temp=18.0, heating_active=False)
        self.assertTrue(state.valve_stuck_open)
        self.assertTrue(state.any_alert)
        self.assertEqual(state.active_problem_type, "valve_stuck_open")
        self.assertIn("Kalkblockade", state.active_problem_description)

        # Room cools down back below delta threshold
        self.clock["now"] = _B0 + timedelta(minutes=50)
        state_cleared = self.mgr.check_safety(current_temp=18.5, target_temp=18.0, heating_active=False)
        self.assertFalse(state_cleared.valve_stuck_open)
        self.assertFalse(state_cleared.any_alert)

    def test_passive_warming_suppressed_by_cold_trv(self):
        """Passive warming from adjacent rooms (cold TRV) does NOT trigger Kalkblockade."""
        # Bad / Eingang at 20.8°C with target 18.0°C.
        # TRV sensor is at 20.9°C (radiator cold / ambient, <= current_temp + 1.5°C).
        self.mgr.check_safety(
            current_temp=20.0,
            target_temp=18.0,
            heating_active=False,
            trv_temperatures=[20.1],
        )
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(
            current_temp=20.8,
            target_temp=18.0,
            heating_active=False,
            trv_temperatures=[20.9],
        )
        self.assertFalse(state.valve_stuck_open)
        self.assertFalse(state.any_alert)

    def test_hot_trv_triggers_kalkblockade(self):
        """Radiator TRV physically hot (> current_temp + 1.5) triggers Kalkblockade."""
        self.mgr.check_safety(
            current_temp=20.0,
            target_temp=18.0,
            heating_active=False,
            trv_temperatures=[30.0],
        )
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(
            current_temp=20.8,
            target_temp=18.0,
            heating_active=False,
            trv_temperatures=[35.0],
        )
        self.assertTrue(state.valve_stuck_open)
        self.assertTrue(state.any_alert)

    def test_heating_failure_diagnoses_trv_not_responding_when_trv_at_5deg(self):
        """Heating failure alerts specifically if physical TRV remains at 5°C despite heat demand."""
        self.mgr.check_safety(
            current_temp=18.0,
            target_temp=22.0,
            heating_active=True,
            trv_targets=[5.0],
        )
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(
            current_temp=18.0,
            target_temp=22.0,
            heating_active=True,
            trv_targets=[5.0],
        )
        self.assertTrue(state.heating_failure)
        self.assertIn("Thermostat übernimmt Heizbefehl nicht", state.active_problem_description)

    def test_heating_failure_suppressed_when_trv_is_actively_hot(self):
        """Heating failure is suppressed if radiator TRV is actively hot (heating is physically working)."""
        self.mgr.check_safety(
            current_temp=18.0,
            target_temp=22.0,
            heating_active=True,
            trv_temperatures=[30.0],
        )
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(
            current_temp=18.0,
            target_temp=22.0,
            heating_active=True,
            trv_temperatures=[30.0],
        )
        self.assertFalse(state.heating_failure)

    def test_heating_failure_detection(self):
        """Detect boiler failure / stuck closed valve when room fails to warm up."""
        # Target 21.0, room at 19.0 (-2.0°C). Heating is active.
        self.mgr.check_safety(current_temp=19.0, target_temp=21.0, heating_active=True)
        self.assertFalse(self.mgr.state.heating_failure)

        # 15 minutes later: room at 19.0°C
        self.clock["now"] = _B0 + timedelta(minutes=15)
        self.mgr.check_safety(current_temp=19.0, target_temp=21.0, heating_active=True)
        self.assertFalse(self.mgr.state.heating_failure)

        # 35 minutes later (> 30 min timeout): room dropped to 18.8°C (no rise >= 0.2°C)
        self.clock["now"] = _B0 + timedelta(minutes=35)
        state = self.mgr.check_safety(current_temp=18.8, target_temp=21.0, heating_active=True)
        self.assertTrue(state.heating_failure)
        self.assertTrue(state.any_alert)
        self.assertEqual(state.active_problem_type, "heating_failure")
        self.assertIn("Heizungsstörung", state.active_problem_description)

        # Later boiler recovers and room heats up
        self.clock["now"] = _B0 + timedelta(minutes=70)
        state_cleared = self.mgr.check_safety(current_temp=21.0, target_temp=21.0, heating_active=False)
        self.assertFalse(state_cleared.heating_failure)
        self.assertFalse(state_cleared.any_alert)

    def test_absolute_overheat_and_frost(self):
        """Check absolute temperature bounds (28°C ceiling, 5°C floor)."""
        state_overheat = self.mgr.check_safety(current_temp=29.0, target_temp=21.0, heating_active=True)
        self.assertTrue(state_overheat.overheat_active)
        self.assertEqual(state_overheat.active_problem_type, "overheat")

        mgr_frost = SafetyManager("Schlafzimmer")
        state_frost = mgr_frost.check_safety(current_temp=4.0, target_temp=18.0, heating_active=False)
        self.assertTrue(state_frost.frost_active)
        self.assertEqual(state_frost.active_problem_type, "frost")


if __name__ == "__main__":
    unittest.main()
