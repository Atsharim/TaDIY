"""Unit tests for Climate entity HVAC mode and action logic (K-06)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

_TEST_ROOT = Path(__file__).resolve().parents[1]
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))


def _install_stubs():
    if "voluptuous" not in sys.modules:
        vol = types.ModuleType("voluptuous")
        vol.Schema = MagicMock()
        vol.Required = MagicMock()
        vol.Optional = MagicMock()
        vol.In = MagicMock()
        vol.Coerce = MagicMock()
        sys.modules["voluptuous"] = vol
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
        def callback(fn):
            return fn
        ha_core.HomeAssistant = HomeAssistant
        ha_core.callback = callback
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
        ha_dt.utcnow = utcnow
        sys.modules["homeassistant.util.dt"] = ha_dt
        ha_util.dt = ha_dt

    if "homeassistant.const" not in sys.modules:
        ha_const = types.ModuleType("homeassistant.const")
        class UnitOfTemperature:
            CELSIUS = "°C"
        ha_const.UnitOfTemperature = UnitOfTemperature
        ha_const.ATTR_TEMPERATURE = "temperature"
        ha_const.STATE_UNAVAILABLE = "unavailable"
        ha_const.STATE_UNKNOWN = "unknown"
        ha_const.Platform = MagicMock()
        sys.modules["homeassistant.const"] = ha_const

    if "homeassistant.config_entries" not in sys.modules:
        ha_cfg = types.ModuleType("homeassistant.config_entries")
        class ConfigEntry:
            entry_id = "test_entry"
        ha_cfg.ConfigEntry = ConfigEntry
        sys.modules["homeassistant.config_entries"] = ha_cfg

    if "homeassistant.components" not in sys.modules:
        ha_comp = types.ModuleType("homeassistant.components")
        ha_comp.__path__ = []
        sys.modules["homeassistant.components"] = ha_comp

    if "homeassistant.components.climate" not in sys.modules:
        ha_clim = types.ModuleType("homeassistant.components.climate")
        class HVACMode(str, Enum):
            OFF = "off"
            HEAT = "heat"
            AUTO = "auto"
        class HVACAction(str, Enum):
            OFF = "off"
            HEATING = "heating"
            IDLE = "idle"
        class ClimateEntityFeature:
            TARGET_TEMPERATURE = 1
            TURN_OFF = 256
            TURN_ON = 512
        class ClimateEntity:
            pass
        ha_clim.HVACMode = HVACMode
        ha_clim.HVACAction = HVACAction
        ha_clim.ClimateEntityFeature = ClimateEntityFeature
        ha_clim.ClimateEntity = ClimateEntity
        sys.modules["homeassistant.components.climate"] = ha_clim

    if "homeassistant.helpers" not in sys.modules:
        ha_hlp = types.ModuleType("homeassistant.helpers")
        ha_hlp.__path__ = []
        sys.modules["homeassistant.helpers"] = ha_hlp

    if "homeassistant.helpers.entity_platform" not in sys.modules:
        ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
        ha_ep.AddEntitiesCallback = MagicMock()
        sys.modules["homeassistant.helpers.entity_platform"] = ha_ep

    if "homeassistant.helpers.update_coordinator" not in sys.modules:
        ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
        class CoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator
            def async_write_ha_state(self):
                pass
        ha_uc.CoordinatorEntity = CoordinatorEntity
        sys.modules["homeassistant.helpers.update_coordinator"] = ha_uc

    if "homeassistant.helpers.storage" not in sys.modules:
        ha_st = types.ModuleType("homeassistant.helpers.storage")
        class Store:
            def __init__(self, *args, **kwargs):
                pass
        ha_st.Store = Store
        sys.modules["homeassistant.helpers.storage"] = ha_st

    if "homeassistant.helpers.event" not in sys.modules:
        ha_ev = types.ModuleType("homeassistant.helpers.event")
        ha_ev.async_track_state_change_event = MagicMock()
        sys.modules["homeassistant.helpers.event"] = ha_ev

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

from custom_components.tadiy.climate import TaDIYClimateEntity
from custom_components.tadiy.core.orchestrator import RoomOrchestrator
from custom_components.tadiy.core.room import RoomData
from custom_components.tadiy.core.window import WindowState
from homeassistant.components.climate import HVACAction, HVACMode


class DummyCoordinator:
    """Mock coordinator for climate tests."""

    def __init__(self):
        self._manual_room_off = False
        self._commanded_target = 21.0
        self._commanded_hvac_mode = "heat"
        self._hub_mode = "normal"
        self.data = MagicMock(spec=RoomData)
        self.data.heating_active = False
        self.data.hvac_mode = "heat"
        self.data.current_temperature = 21.2
        self.data.target_temperature = 21.0
        self.data.window_state = WindowState(is_open=False, heating_should_stop=False)
        self.hass = MagicMock()
        self.hass.services.async_call = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.room_config = MagicMock()
        self.room_config.name = "Living Room"
        self.room_config.trv_entity_ids = ["climate.trv_1"]
        self.room_config.away_temperature = 16.0
        self.room_config.target_temp_step = 0.5
        self.hub_coordinator = MagicMock()
        self.hub_coordinator.get_frost_protection_temp.return_value = 5.0
        self.hub_coordinator.should_reduce_heating_for_away.return_value = False
        self.override_manager = MagicMock()
        self.calibration_manager = MagicMock()
        self.current_room_data = self.data

    def get_hub_mode(self) -> str:
        return self._hub_mode

    def is_manual_room_off(self) -> bool:
        return self._manual_room_off

    def set_manual_room_off(self, value: bool) -> None:
        self._manual_room_off = value
        self._commanded_hvac_mode = "off" if value else "heat"

    def notify_user_interaction(self) -> None:
        pass

    def get_scheduled_target(self) -> float:
        return 21.0

    def get_override_timeout(self) -> str:
        return "next_block"

    def debug(self, *args, **kwargs) -> None:
        pass


class TestClimateModeAndAction(unittest.TestCase):
    """Test HVAC mode and action logic according to K-06."""

    def setUp(self):
        self.coord = DummyCoordinator()
        self.entry = MagicMock()
        self.entry.entry_id = "test_entry"
        with patch("custom_components.tadiy.climate.get_device_info", return_value={}):
            self.entity = TaDIYClimateEntity(
                coordinator=self.coord,
                room_name="Living Room",
                trv_entity_ids=["climate.trv_1"],
                entry=self.entry,
            )
            self.entity.hass = self.coord.hass

    def test_normal_heating_idle_when_target_reached(self):
        """Room at target: mode is HEAT, action is IDLE (not OFF)."""
        self.coord.data.heating_active = False
        self.coord._commanded_hvac_mode = "heat"

        self.assertEqual(self.entity.hvac_mode, HVACMode.HEAT)
        self.assertEqual(self.entity.hvac_action, HVACAction.IDLE)

    def test_normal_heating_active(self):
        """Room heating: mode is HEAT, action is HEATING."""
        self.coord.data.heating_active = True
        self.coord._commanded_hvac_mode = "heat"

        self.assertEqual(self.entity.hvac_mode, HVACMode.HEAT)
        self.assertEqual(self.entity.hvac_action, HVACAction.HEATING)

    def test_hub_mode_off_forces_climate_off(self):
        """Hub mode 'off': mode is OFF, action is OFF."""
        self.coord._hub_mode = "off"
        self.coord._commanded_hvac_mode = "off"

        self.assertEqual(self.entity.hvac_mode, HVACMode.OFF)
        self.assertEqual(self.entity.hvac_action, HVACAction.OFF)

    def test_window_open_stop_forces_climate_off(self):
        """Window open heating_should_stop: mode is OFF, action is OFF."""
        self.coord.data.window_state = WindowState(is_open=True, heating_should_stop=True)
        self.coord._commanded_hvac_mode = "off"

        self.assertEqual(self.entity.hvac_mode, HVACMode.OFF)
        self.assertEqual(self.entity.hvac_action, HVACAction.OFF)

    def test_manual_room_off(self):
        """User turning room off sets mode OFF and action OFF."""
        self.coord.set_manual_room_off(True)

        self.assertEqual(self.entity.hvac_mode, HVACMode.OFF)
        self.assertEqual(self.entity.hvac_action, HVACAction.OFF)

    def test_async_turn_off_and_on(self):
        """Calling async_turn_off and async_turn_on toggles manual room off."""
        asyncio.run(self.entity.async_turn_off())
        self.assertTrue(self.coord.is_manual_room_off())
        self.assertEqual(self.entity.hvac_mode, HVACMode.OFF)

        asyncio.run(self.entity.async_turn_on())
        self.assertFalse(self.coord.is_manual_room_off())
        self.assertEqual(self.entity.hvac_mode, HVACMode.HEAT)

    def test_orchestrator_manual_room_off_returns_frost_target(self):
        """Orchestrator enforces frost target when room is manually off."""
        orch = RoomOrchestrator(self.coord)
        self.coord._manual_room_off = True

        target, enforce = orch.calculate_target_temperature(
            scheduled_target=21.0,
            active_override_target=None,
            hub_mode="normal",
            outdoor_temp=10.0,
            window_should_stop=False,
        )

        self.assertEqual(target, 5.0)
        self.assertTrue(enforce)

    def test_current_humidity_and_comfort_attributes(self):
        """Climate entity exposes humidity and comfort attributes for robust panel discovery (K-02)."""
        self.coord.data.humidity = 55.4
        self.coord.data.current_temperature = 21.0

        self.assertEqual(self.entity.current_humidity, 55.4)

        attrs = self.entity.extra_state_attributes
        self.assertEqual(attrs["integration"], "tadiy")
        self.assertEqual(attrs["room_name"], "Living Room")
        self.assertEqual(attrs["entry_id"], "test_entry")
        self.assertIn("comfort_score", attrs)
        self.assertIn("comfort_level", attrs)
        self.assertIn("comfort_color", attrs)


if __name__ == "__main__":
    unittest.main()
