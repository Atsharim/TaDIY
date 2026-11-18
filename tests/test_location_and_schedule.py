"""Unit tests for LocationManager and Homeoffice Feierabend-Rückfall schedule logic."""

from __future__ import annotations

import importlib
from datetime import datetime, time, timedelta, timezone
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

location_mod = importlib.import_module("custom_components.tadiy.core.location")
from custom_components.tadiy.core.location import (
    LocationManager,
    AWAY_GRACE_PERIOD,
    AWAY_PARTIAL_PERIOD,
)
from custom_components.tadiy.core.schedule_model import (
    RoomSchedule,
    DaySchedule,
    ScheduleBlock,
    SCHEDULE_TYPE_DAILY,
)

_B0 = datetime(2026, 11, 11, 14, 0, 0, tzinfo=timezone.utc)


class TestLocationManager(unittest.TestCase):
    """Test LocationManager manual override and away duration handling (K-12)."""

    def setUp(self) -> None:
        self.clock = {"now": _B0}
        for name in ("utcnow", "now"):
            patcher = patch.object(
                location_mod.dt_util,
                name,
                side_effect=lambda: self.clock["now"],
                create=True,
            )
            patcher.start()
            self.addCleanup(patcher.stop)

        self.hass = MagicMock()
        self.mgr = LocationManager(self.hass, ["person.alice"])

    def test_manual_override_away_immediate(self):
        """Forced away with immediate=True applies full reduction immediately."""
        self.mgr.set_manual_override(False, immediate=True)
        self.assertTrue(self.mgr.is_away_mode_active())
        self.assertGreaterEqual(self.mgr.get_away_duration_seconds(), AWAY_PARTIAL_PERIOD)
        target = self.mgr.get_gradual_away_target(scheduled_target=21.0, away_target=17.0)
        self.assertEqual(target, 17.0)

    def test_manual_override_away_gradual(self):
        """Forced away with immediate=False starts gradual timer from 0s (grace period)."""
        self.mgr.set_manual_override(False, immediate=False)
        self.assertTrue(self.mgr.is_away_mode_active())
        # In grace period (<30 min), scheduled target is retained
        target = self.mgr.get_gradual_away_target(scheduled_target=21.0, away_target=17.0)
        self.assertEqual(target, 21.0)

        # Advance clock by 40 minutes (partial period)
        self.clock["now"] = _B0 + timedelta(minutes=40)
        target_partial = self.mgr.get_gradual_away_target(scheduled_target=21.0, away_target=17.0)
        self.assertEqual(target_partial, 19.0)  # 21 - 2 = 19

        # Advance clock past 2 hours (full reduction)
        self.clock["now"] = _B0 + timedelta(hours=3)
        target_full = self.mgr.get_gradual_away_target(scheduled_target=21.0, away_target=17.0)
        self.assertEqual(target_full, 17.0)

    def test_manual_override_home_clears_away(self):
        """Forced home clears away_since and returns scheduled target."""
        self.mgr.set_manual_override(False, immediate=True)
        self.assertTrue(self.mgr.is_away_mode_active())

        self.mgr.set_manual_override(True)
        self.assertFalse(self.mgr.is_away_mode_active())
        self.assertEqual(self.mgr.get_away_duration_seconds(), 0.0)
        target = self.mgr.get_gradual_away_target(scheduled_target=21.0, away_target=17.0)
        self.assertEqual(target, 21.0)

    def test_persistence_roundtrip(self):
        """Manager serializes and restores override and away_since timestamp."""
        self.mgr.set_manual_override(False, immediate=False)
        saved = self.mgr.to_dict()
        self.assertEqual(saved["manual_override"], False)
        self.assertIsNotNone(saved["away_since"])

        restored_mgr = LocationManager(self.hass, ["person.alice"])
        restored_mgr.restore_from_dict(saved)
        self.assertTrue(restored_mgr.is_away_mode_active())
        self.assertIsNotNone(restored_mgr._away_since)


class TestHomeofficeScheduleLogic(unittest.TestCase):
    """Test Homeoffice Feierabend-Rückfall schedule switching."""

    def setUp(self) -> None:
        # Create schedules for room
        weekday_blocks = [
            ScheduleBlock(time(0, 0), 18.0),
            ScheduleBlock(time(6, 0), 21.0),
            ScheduleBlock(time(8, 0), 18.0),  # Office day off-peak
            ScheduleBlock(time(17, 0), 21.5),  # Evening comfortable
            ScheduleBlock(time(22, 0), 18.0),
        ]
        weekend_blocks = [
            ScheduleBlock(time(0, 0), 18.0),
            ScheduleBlock(time(8, 0), 22.0),
            ScheduleBlock(time(23, 0), 18.0),
        ]
        homeoffice_blocks = [
            ScheduleBlock(time(0, 0), 18.0),
            ScheduleBlock(time(7, 0), 21.0),  # All-day warm
            ScheduleBlock(time(22, 0), 18.0),
        ]
        self.normal_weekday = DaySchedule(SCHEDULE_TYPE_DAILY, weekday_blocks)
        self.normal_weekend = DaySchedule(SCHEDULE_TYPE_DAILY, weekend_blocks)
        self.homeoffice_daily = DaySchedule(SCHEDULE_TYPE_DAILY, homeoffice_blocks)

        self.schedule = RoomSchedule(
            room_name="Wohnzimmer",
            normal_weekday=self.normal_weekday,
            normal_weekend=self.normal_weekend,
            homeoffice_daily=self.homeoffice_daily,
        )

    def test_homeoffice_during_day(self):
        """During work hours on Wednesday (14:00), homeoffice schedule is active."""
        wednesday_14 = datetime(2026, 11, 11, 14, 0, 0)
        sched = self.schedule.get_schedule_for_mode(
            mode="homeoffice",
            dt=wednesday_14,
            homeoffice_end_hour=17,
        )
        self.assertIs(sched, self.homeoffice_daily)

    def test_homeoffice_reverts_after_end_hour(self):
        """After Feierabend (17:30) on Wednesday, schedule reverts to normal weekday schedule."""
        wednesday_1730 = datetime(2026, 11, 11, 17, 30, 0)
        sched = self.schedule.get_schedule_for_mode(
            mode="homeoffice",
            dt=wednesday_1730,
            homeoffice_end_hour=17,
        )
        self.assertIs(sched, self.normal_weekday)
        # Check that temperature corresponds to normal weekday evening (21.5°C)
        self.assertEqual(sched.get_temperature(time(17, 30), 12.0), 21.5)

    def test_homeoffice_friday_evening_reverts_to_weekend_if_friday_weekend_active(self):
        """On Friday evening with friday_weekend_start_hour=16, reverts to weekend schedule."""
        friday_18 = datetime(2026, 11, 13, 18, 0, 0)
        sched = self.schedule.get_schedule_for_mode(
            mode="homeoffice",
            dt=friday_18,
            friday_weekend_start_hour=16,
            homeoffice_end_hour=17,
        )
        self.assertIs(sched, self.normal_weekend)
        self.assertEqual(sched.get_temperature(time(18, 0), 12.0), 22.0)

    def test_homeoffice_weekend_not_affected(self):
        """On Saturday, homeoffice schedule is used if homeoffice mode is explicitly set."""
        saturday_18 = datetime(2026, 11, 14, 18, 0, 0)
        sched = self.schedule.get_schedule_for_mode(
            mode="homeoffice",
            dt=saturday_18,
            homeoffice_end_hour=17,
        )
        self.assertIs(sched, self.homeoffice_daily)


class TestHomeofficeTomorrow(unittest.TestCase):
    """Test Homeoffice Tomorrow scheduling logic."""

    def test_homeoffice_tomorrow_activation_on_rollover(self):
        """When homeoffice_tomorrow is scheduled and date advances, it activates homeoffice today."""
        from datetime import date
        # Mock a coordinator object with homeoffice_tomorrow logic
        class CoordinatorMock:
            def __init__(self):
                self._homeoffice_tomorrow = True
                self._homeoffice_tomorrow_set_date = date(2026, 11, 12)
                self.hub_mode = "normal"
                self._homeoffice_started_date = None

            def set_hub_mode(self, mode):
                self.hub_mode = mode
                if mode == "homeoffice":
                    self._homeoffice_started_date = date(2026, 11, 13)

            def update_rollover(self, current_date):
                if self._homeoffice_tomorrow:
                    set_date = self._homeoffice_tomorrow_set_date
                    if set_date is not None and current_date > set_date:
                        self._homeoffice_tomorrow = False
                        self._homeoffice_tomorrow_set_date = None
                        self.set_hub_mode("homeoffice")

        c = CoordinatorMock()
        # Same day: should not activate yet
        c.update_rollover(date(2026, 11, 12))
        self.assertTrue(c._homeoffice_tomorrow)
        self.assertEqual(c.hub_mode, "normal")

        # Next day: activates homeoffice mode and clears tomorrow flag
        c.update_rollover(date(2026, 11, 13))
        self.assertFalse(c._homeoffice_tomorrow)
        self.assertEqual(c.hub_mode, "homeoffice")
        self.assertEqual(c._homeoffice_started_date, date(2026, 11, 13))


if __name__ == "__main__":
    unittest.main()
