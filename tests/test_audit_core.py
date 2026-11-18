"""Unit tests for audited core modules: calibration, weather, coupling, valve_protection (K-08)."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock

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
        class Event:
            pass
        class Context:
            pass
        def callback(fn):
            return fn
        ha_core.HomeAssistant = HomeAssistant
        ha_core.Event = Event
        ha_core.Context = Context
        ha_core.callback = callback
        sys.modules["homeassistant.core"] = ha_core
        ha.core = ha_core
    else:
        ha_core = sys.modules["homeassistant.core"]
        if not hasattr(ha_core, "Event"):
            class Event:
                pass
            ha_core.Event = Event
        if not hasattr(ha_core, "Context"):
            class Context:
                pass
            ha_core.Context = Context
        if not hasattr(ha_core, "callback"):
            def callback(fn):
                return fn
            ha_core.callback = callback

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
        def as_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        def as_local(dt: datetime) -> datetime:
            return dt
        ha_dt.utcnow = utcnow
        ha_dt.now = now
        ha_dt.as_utc = as_utc
        ha_dt.as_local = as_local
        sys.modules["homeassistant.util.dt"] = ha_dt
        ha_util.dt = ha_dt
    else:
        ha_dt = sys.modules["homeassistant.util.dt"]
        if not hasattr(ha_dt, "as_utc"):
            def as_utc(dt: datetime) -> datetime:
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            ha_dt.as_utc = as_utc
        if not hasattr(ha_dt, "as_local"):
            def as_local(dt: datetime) -> datetime:
                return dt
            ha_dt.as_local = as_local

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
        ha.components = ha_comp

    if "homeassistant.components.binary_sensor" not in sys.modules:
        ha_bs = types.ModuleType("homeassistant.components.binary_sensor")
        class BinarySensorDeviceClass:
            PROBLEM = "problem"
            WINDOW = "window"
        class BinarySensorEntity:
            _attr_has_entity_name = True
            _attr_device_class = None
            _attr_entity_category = None
            _attr_icon = None
            @property
            def device_class(self):
                return self._attr_device_class
            def async_write_ha_state(self):
                pass
        ha_bs.BinarySensorDeviceClass = BinarySensorDeviceClass
        ha_bs.BinarySensorEntity = BinarySensorEntity
        sys.modules["homeassistant.components.binary_sensor"] = ha_bs

    if "homeassistant.components.select" not in sys.modules:
        ha_sel = types.ModuleType("homeassistant.components.select")
        class SelectEntity:
            _attr_has_entity_name = True
            def __init__(self, *args, **kwargs):
                pass
        class SelectEntityDescription:
            def __init__(self, key="", name="", icon=None):
                self.key = key
                self.name = name
                self.icon = icon
        ha_sel.SelectEntity = SelectEntity
        ha_sel.SelectEntityDescription = SelectEntityDescription
        sys.modules["homeassistant.components.select"] = ha_sel

    if "homeassistant.helpers" not in sys.modules:
        ha_helpers = types.ModuleType("homeassistant.helpers")
        ha_helpers.__path__ = []
        sys.modules["homeassistant.helpers"] = ha_helpers
        ha.helpers = ha_helpers

    if "homeassistant.helpers.entity" not in sys.modules:
        ha_entity = types.ModuleType("homeassistant.helpers.entity")
        class EntityCategory:
            DIAGNOSTIC = "diagnostic"
            CONFIG = "config"
        ha_entity.EntityCategory = EntityCategory
        sys.modules["homeassistant.helpers.entity"] = ha_entity

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
        class DataUpdateCoordinator:
            def __init__(self, *args, **kwargs):
                pass
        class UpdateFailed(Exception):
            pass
        ha_uc.CoordinatorEntity = CoordinatorEntity
        ha_uc.DataUpdateCoordinator = DataUpdateCoordinator
        ha_uc.UpdateFailed = UpdateFailed
        sys.modules["homeassistant.helpers.update_coordinator"] = ha_uc

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

from custom_components.tadiy.core.calibration import CalibrationManager
from custom_components.tadiy.core.room_coupling import RoomCouplingManager
from custom_components.tadiy.core.valve_protection import ValveProtectionManager
from custom_components.tadiy.core.weather_predictor import WeatherPredictor


class TestCalibrationManager(unittest.TestCase):
    """Test TRV calibration fixes (K-08)."""

    def setUp(self):
        self.mgr = CalibrationManager()

    def test_disabled_mode_ignores_previous_offset(self):
        """Disabled mode returns exact target regardless of prior auto-learned offset."""
        # 1. TRV learns an offset in auto mode
        self.mgr.get_calibrated_target("climate.trv_1", target_temp=21.0, room_temp=20.0, trv_temp=24.0)
        cal = self.mgr._calibrations["climate.trv_1"]
        self.assertEqual(cal.offset, 4.0)

        # 2. Disable calibration
        self.mgr.set_mode("climate.trv_1", "disabled")
        target = self.mgr.get_calibrated_target("climate.trv_1", target_temp=21.0, room_temp=20.0, trv_temp=24.0)
        self.assertEqual(target, 21.0)

    def test_manual_mode_applies_offset_without_sensor_temps(self):
        """Manual mode applies static offset even when room_temp or trv_temp is None."""
        self.mgr.set_manual_offset("climate.trv_1", offset=2.5)

        target = self.mgr.get_calibrated_target("climate.trv_1", target_temp=20.0, room_temp=None, trv_temp=None)
        self.assertEqual(target, 22.5)

    def test_manual_mode_clamps_at_max_temp(self):
        """Manual offset respects max_temp clamping."""
        self.mgr.set_manual_offset("climate.trv_1", offset=5.0)
        target = self.mgr.get_calibrated_target("climate.trv_1", target_temp=28.0, max_temp=30.0)
        self.assertEqual(target, 30.0)

    def test_multi_trv_independent_calibration(self):
        """Each TRV in a multi-radiator room learns independent calibration offsets."""
        # TRV 1: Near cold window, internal sensor reads 22.0°C when room is 20.0°C -> offset +2.0
        # TRV 2: Deep in niche, internal sensor reads 25.0°C when room is 20.0°C -> offset +5.0
        target_room = 21.0
        cal_1 = self.mgr.get_calibrated_target(
            "climate.trv_window", target_temp=target_room, room_temp=20.0, trv_temp=22.0
        )
        cal_2 = self.mgr.get_calibrated_target(
            "climate.trv_niche", target_temp=target_room, room_temp=20.0, trv_temp=25.0
        )
        self.assertEqual(cal_1, 23.0)  # 21.0 + 2.0
        self.assertEqual(cal_2, 26.0)  # 21.0 + 5.0
        self.assertNotEqual(
            self.mgr._calibrations["climate.trv_window"].offset,
            self.mgr._calibrations["climate.trv_niche"].offset,
        )


class TestWeatherPredictor(unittest.TestCase):
    """Test weather predictor timezone handling and cold/warm front detection (K-08)."""

    def setUp(self):
        self.hass = MagicMock()
        self.predictor = WeatherPredictor(self.hass, "weather.forecast_home")

    def test_forecast_parsing_handles_naive_and_iso_datetimes(self):
        """Forecast datetimes without timezone offset are converted to UTC without crashing."""
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        with unittest.mock.patch("homeassistant.util.dt.utcnow", return_value=now):
            # Simulate service response with string ISO datetime
            self.hass.services.async_call = AsyncMock(return_value={
                "weather.forecast_home": {
                    "forecast": [
                        {"datetime": "2026-11-12T13:00:00", "temperature": 8.0},
                        {"datetime": "2026-11-12T14:00:00", "temperature": 4.0},
                    ]
                }
            })
            success = asyncio.run(self.predictor.async_update_forecast())
            self.assertTrue(success)
            self.assertEqual(len(self.predictor._last_forecast), 2)

    def test_cold_front_prediction(self):
        """Sudden temperature drop triggers preheat recommendation."""
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        with unittest.mock.patch("homeassistant.util.dt.utcnow", return_value=now):
            self.hass.services.async_call = AsyncMock(return_value={
                "weather.forecast_home": {
                    "forecast": [
                        {"datetime": "2026-11-12T13:00:00+00:00", "temperature": 2.0},  # drop of 6°C
                    ]
                }
            })
            asyncio.run(self.predictor.async_update_forecast())
            prediction = self.predictor.predict_heating_adjustment(current_outdoor_temp=8.0)

            self.assertEqual(prediction.predicted_event, "cold_front")
            self.assertEqual(prediction.recommendation, "preheat")
            self.assertGreater(prediction.adjustment_celsius, 0.0)


class TestRoomCoupling(unittest.TestCase):
    """Test room coupling logic (K-08)."""

    def setUp(self):
        self.mgr = RoomCouplingManager()
        self.mgr.register_room("Living Room", adjacent_rooms=["Kitchen"], coupling_strength=0.5)

    def test_cold_unheated_room_does_not_heat_neighbors(self):
        """When is_heating is False, room must not be marked as actively heating even if colder than target."""
        # Kitchen is at 18°C with target 21°C, but heating is OFF (e.g. window open or manual off)
        self.mgr.update_room_heating_status(
            room_name="Kitchen",
            is_heating=False,
            current_temp=18.0,
            target_temp=21.0,
        )

        state = self.mgr.get_room_state("Living Room")
        self.assertNotIn("Kitchen", state.neighbors_heating)
        self.assertEqual(self.mgr.get_coupling_adjustment("Living Room"), 0.0)

    def test_actively_heating_room_reduces_neighbor_target(self):
        """When neighbor is actively heating, target is reduced by coupling strength."""
        self.mgr.update_room_heating_status(
            room_name="Kitchen",
            is_heating=True,
            current_temp=18.0,
            target_temp=21.0,
        )

        state = self.mgr.get_room_state("Living Room")
        self.assertIn("Kitchen", state.neighbors_heating)

        # 1 neighbor * 0.5 base * 0.5 strength = -0.25°C
        adjustment = self.mgr.get_coupling_adjustment("Living Room")
        self.assertAlmostEqual(adjustment, -0.25, places=2)


class TestValveProtection(unittest.TestCase):
    """Test valve protection lifecycle (K-08)."""

    def setUp(self):
        self.mgr = ValveProtectionManager(
            room_name="Bedroom",
            cycle_day=0,  # Monday
            cycle_time=time(10, 0),
            cycle_interval_weeks=2,
        )

    def test_lifecycle_opening_closing_done(self):
        """Valve protection cycles through opening -> closing -> done."""
        start_time = datetime(2026, 11, 12, 10, 0, 0, tzinfo=timezone.utc)

        with unittest.mock.patch("homeassistant.util.dt.utcnow", return_value=start_time):
            open_temp = self.mgr.start_cycle()
            self.assertEqual(open_temp, 30.0)
            self.assertTrue(self.mgr.state.cycling_active)

            phase, temp = self.mgr.update_cycle()
            self.assertEqual(phase, "opening")
            self.assertEqual(temp, 30.0)

        # 130s elapsed -> closing phase
        with unittest.mock.patch("homeassistant.util.dt.utcnow", return_value=start_time + timedelta(seconds=130)):
            phase, temp = self.mgr.update_cycle()
            self.assertEqual(phase, "closing")
            self.assertEqual(temp, 5.0)

        # 250s elapsed -> done
        with unittest.mock.patch("homeassistant.util.dt.utcnow", return_value=start_time + timedelta(seconds=250)):
            phase, temp = self.mgr.update_cycle()
            self.assertEqual(phase, "done")
            self.assertIsNone(temp)
            self.assertFalse(self.mgr.state.cycling_active)


class TestRoomWindowBinarySensor(unittest.TestCase):
    """Test window binary sensor entity on the room device."""

    def setUp(self):
        from custom_components.tadiy.binary_sensor import TaDIYRoomWindowBinarySensor
        from custom_components.tadiy.core.window import WindowState

        self.WindowState = WindowState
        self.coordinator = MagicMock()
        self.coordinator.hass = MagicMock()
        self.coordinator.room_config = MagicMock()
        self.coordinator.room_config.name = "Living Room"
        self.coordinator.room_config.window_sensor_ids = ["binary_sensor.living_window"]

        self.entry = MagicMock()
        self.entry.entry_id = "test_room_123"
        self.entry.title = "Living Room"
        self.entry.data = {"room_name": "Living Room"}

        self.sensor = TaDIYRoomWindowBinarySensor(self.coordinator, self.entry)

    def test_window_closed(self):
        """Sensor reports off when window is closed."""
        self.coordinator.data = MagicMock()
        self.coordinator.data.window_state = self.WindowState(
            is_open=False,
            reason="window_closed",
            heating_should_stop=False,
        )
        self.assertFalse(self.sensor.is_on)
        self.assertEqual(self.sensor.device_class, "window")

    def test_window_open_within_grace(self):
        """Sensor reports on even during grace period before heating stops."""
        self.coordinator.data = MagicMock()
        self.coordinator.data.window_state = self.WindowState(
            is_open=True,
            reason="window_open_within_timeout",
            heating_should_stop=False,
            timeout_active=True,
        )
        self.assertTrue(self.sensor.is_on)
        attrs = self.sensor.extra_state_attributes
        self.assertFalse(attrs["heating_should_stop"])
        self.assertTrue(attrs["timeout_active"])
        self.assertEqual(attrs["detection_method"], "contact_sensor")

    def test_window_open_heating_stopped(self):
        """Sensor reports on and heating_should_stop is True after timeout."""
        self.coordinator.data = MagicMock()
        self.coordinator.data.window_state = self.WindowState(
            is_open=True,
            reason="window_open_heating_disabled",
            heating_should_stop=True,
            timeout_active=False,
        )
        self.assertTrue(self.sensor.is_on)
        attrs = self.sensor.extra_state_attributes
        self.assertTrue(attrs["heating_should_stop"])
        self.assertEqual(attrs["reason"], "window_open_heating_disabled")


class TestHubCoordinatorAndBoiler(unittest.TestCase):
    """Test Hub coordinator setter and boiler temperature sensor handling."""

    def test_room_coordinator_hub_setter(self):
        """Verify room coordinator hub_coordinator has setter to prevent crash."""
        from custom_components.tadiy.coordinator import TaDIYRoomCoordinator
        prop = getattr(TaDIYRoomCoordinator, "hub_coordinator")
        self.assertIsNotNone(prop.fset, "hub_coordinator must have a setter")

    def test_boiler_binary_sensor_active(self):
        """Test boiler binary sensor reports on when boiler >= 45°C."""
        from custom_components.tadiy.binary_sensor import TaDIYHubBoilerBinarySensor
        coordinator = MagicMock()
        coordinator.data = {
            "boiler_active": True,
            "boiler_temperature": 55.4,
            "boiler_sensor_available": True,
            "boiler_temp_sensor_id": "sensor.boilertemperatur_temperature_probe",
        }
        coordinator.hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "hub_123"
        sensor = TaDIYHubBoilerBinarySensor(coordinator, entry)
        self.assertTrue(sensor.is_on)
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["boiler_temperature"], 55.4)
        self.assertTrue(attrs["sensor_available"])

    def test_boiler_binary_sensor_inactive(self):
        """Test boiler binary sensor reports off when boiler < 45°C."""
        from custom_components.tadiy.binary_sensor import TaDIYHubBoilerBinarySensor
        coordinator = MagicMock()
        coordinator.data = {
            "boiler_active": False,
            "boiler_temperature": 28.1,
            "boiler_sensor_available": True,
        }
        coordinator.hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "hub_123"
        sensor = TaDIYHubBoilerBinarySensor(coordinator, entry)
        self.assertFalse(sensor.is_on)

    def test_hub_coordinator_init_attributes(self):
        """Test TaDIYHubCoordinator initializes without AttributeError."""
        from custom_components.tadiy.coordinator import TaDIYHubCoordinator
        hass = MagicMock()
        hass.states = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_hub_entry"
        entry.data = {"name": "Test Hub"}
        coord = TaDIYHubCoordinator(hass, "test_hub_entry", {}, entry)
        self.assertIsNotNone(coord.global_settings)
        self.assertEqual(coord.person_entities, [])
        self.assertEqual(coord.global_offset_step, 1.5)
        self.assertTrue(coord.window_neighbor_setback_enabled)

    def test_room_config_min_max_temp_properties(self):
        """Test RoomConfig min_temp and max_temp properties exist and return floats."""
        from custom_components.tadiy.core.room import RoomConfig
        cfg = RoomConfig(
            name="Test Room",
            trv_entity_ids=["climate.trv1"],
            main_temp_sensor_id="sensor.temp1",
            trv_min_temp=4.5,
            trv_max_temp=28.0,
        )
        self.assertEqual(cfg.min_temp, 4.5)
        self.assertEqual(cfg.max_temp, 28.0)

    def test_hub_coordinator_mappingproxy_handling(self):
        """Test TaDIYHubCoordinator handles mappingproxy config_data safely."""
        from types import MappingProxyType
        from custom_components.tadiy.coordinator import TaDIYHubCoordinator
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "hub_proxy"
        proxy_data = MappingProxyType({"name": "Proxy Hub", "global_offset_step": 2.0})
        coord = TaDIYHubCoordinator(hass, "hub_proxy", proxy_data, entry)
        self.assertIsInstance(coord.config_data, dict)
        coord.config_data.update({"new_key": "val"})
        self.assertEqual(coord.config_data.get("new_key"), "val")

    def test_location_manager_person_entities_property(self):
        """Test LocationManager person_entities getter and setter alias."""
        from custom_components.tadiy.core.location import LocationManager
        hass = MagicMock()
        lm = LocationManager(hass, ["person.micha"])
        self.assertEqual(lm.person_entities, ["person.micha"])
        lm.person_entities = ["person.micha", "person.dimimon"]
        self.assertEqual(lm.person_entity_ids, ["person.micha", "person.dimimon"])
        self.assertEqual(lm.person_entities, ["person.micha", "person.dimimon"])

    def test_services_yaml_selectors_valid(self):
        """Test services.yaml parses cleanly and every select selector defines 'options'."""
        import os
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed in test environment")

        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "custom_components", "tadiy", "services.yaml"
        )
        self.assertTrue(os.path.exists(yaml_path))
        with open(yaml_path, "r", encoding="utf-8") as f:
            services = yaml.safe_load(f)

        self.assertIn("set_room_config", services)
        self.assertIn("set_hub_config", services)

        # Recursively check that every select selector has 'options' defined
        def check_selectors(data, path=""):
            if isinstance(data, dict):
                for k, v in data.items():
                    current_path = f"{path}.{k}" if path else k
                    if k == "select" and isinstance(v, dict):
                        self.assertIn(
                            "options",
                            v,
                            f"Missing 'options' key in select selector at {current_path}",
                        )
                    check_selectors(v, current_path)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_selectors(item, f"{path}[{i}]")

        check_selectors(services)

    def test_hub_select_extra_attributes_includes_runtime_and_cycle_lock(self):
        """Test hub_mode select entity exposes boiler_min_run_time and cycle_lock."""
        from custom_components.tadiy.select import TaDIYHubSelect, HUB_SELECT_TYPES
        from custom_components.tadiy.const import (
            CONF_BOILER_MIN_RUN_TIME,
            CONF_CYCLE_LOCK_ON_SETPOINT_DROP,
        )
        coord = MagicMock()
        coord.config_data = {
            CONF_BOILER_MIN_RUN_TIME: 450,
            CONF_CYCLE_LOCK_ON_SETPOINT_DROP: False,
        }
        coord.frost_protection_temp = 6.5
        coord.boiler_temp_sensor = "sensor.boiler"
        coord.dhw_temp_sensor = "sensor.dhw"
        coord.boiler_temperature = 55.0
        coord.boiler_sensor_available = True
        coord.boiler_active = True
        coord.dhw_temperature = 48.0
        coord.dhw_sensor_available = True
        coord._homeoffice_tomorrow = False
        coord.person_entities = []
        coord.window_neighbor_setback_enabled = True
        coord.window_neighbor_setback_delta = 1.5
        coord.window_house_setback_delta = 1.0
        coord.global_offset_step = 1.0
        coord.global_offset_mode = "duration"
        coord.global_offset_duration_hours = 2.0
        coord.global_offset_temp = 0.0
        coord.global_offset_until = None

        entity = TaDIYHubSelect(coord, HUB_SELECT_TYPES[0], "test_hub_id")
        attrs = entity.extra_state_attributes
        self.assertEqual(attrs.get(CONF_BOILER_MIN_RUN_TIME), 450)
        self.assertEqual(attrs.get(CONF_CYCLE_LOCK_ON_SETPOINT_DROP), False)
        self.assertEqual(attrs.get("global_offset_mode"), "duration")

    def test_trv_idle_temperature_control_preserves_target_without_slam_to_frost(self):
        """When use_hvac_off_for_low_temp is False and should_heat is False, target is preserved."""
        import asyncio
        from custom_components.tadiy.core.trv_manager import TrvManager
        from custom_components.tadiy.core.room import RoomConfig

        coord = MagicMock()
        coord.room_config = RoomConfig(
            name="Esszimmer",
            trv_entity_ids=["climate.thermostat_essbereich"],
            main_temp_sensor_id="sensor.temp_essbereich",
            use_hvac_off_for_low_temp=False,
            trv_min_temp=5.0,
            trv_max_temp=30.0,
            target_temp_step=0.5,
        )
        coord.get_current_temperature.return_value = 21.2
        coord.hass = MagicMock()
        trv_state = MagicMock()
        trv_state.state = "heat"
        trv_state.attributes = {
            "current_temperature": 23.0,
            "temperature": 21.0,
            "hvac_modes": ["heat", "off"],
        }
        coord.hass.states.get.return_value = trv_state
        coord.hass.services.async_call = AsyncMock()

        mgr = TrvManager(coord)
        asyncio.run(mgr._apply_target_locked(target=21.0, should_heat=False))

        last_cmd = mgr.get_last_commanded("climate.thermostat_essbereich")
        self.assertIsNotNone(last_cmd)
        self.assertEqual(last_cmd["hvac_mode"], "heat")
        self.assertEqual(last_cmd["temperature"], 21.0)



if __name__ == "__main__":
    unittest.main()
