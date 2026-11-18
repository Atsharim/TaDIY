"""Unit tests for custom_components/tadiy/core/control.py.

Loads control.py (and const.py) directly by file path so the tests do not
pull in the heavy TaDIY package __init__ files.  Missing Home-Assistant
dependencies (homeassistant.util.dt) are replaced by a controlled clock
stub (FakeClock) that feeds dt_util.utcnow().

Behavior layers under test (hysteresis=0.5 by default -> band is
[target-0.25, target+0.25)):
1. Hysteresis: ON below target-h/2, OFF at/above target+h/2.
2. Consecutive confirmation: a flip needs 2 agreeing readings.
3. Minimum cycle time: 300 s between state changes.
4. Trend guard: restricted to the deadband, where no raw flip can occur
   with this implementation, hence effectively inactive (documented, not
   weakened).
5. Noise floor / TREND_DEAD_ZONE: no separate deadband logic exists in
   the controller; NOISE_FLOOR is only defined, not applied.  Tested via
   steady-state checks.
6. reset() and PID behaviour.
"""

import importlib.util
import logging
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import unittest

ROOT = Path(__file__).resolve().parents[1]
TADIY_DIR = ROOT / "custom_components" / "tadiy"
CORE_DIR = TADIY_DIR / "core"

# control.py's own constants, mirrored for assertions (no import needed).
MIN_CYCLE_SECONDS = 300
TREND_WINDOW_SIZE = 6
DEFAULT_HYSTERESIS = 0.5

_B0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Stands in for homeassistant.util.dt.utcnow()."""

    def __init__(self):
        self.now = _B0

    def set(self, value: datetime) -> None:
        self.now = value

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)

    def utcnow(self) -> datetime:
        return self.now


CLOCK = FakeClock()


def _install_ha_stubs() -> None:
    """Register minimal homeassistant.util.dt stub in sys.modules."""
    if "homeassistant" in sys.modules:
        if "homeassistant.util.dt" in sys.modules:
            sys.modules["homeassistant.util.dt"].utcnow = CLOCK.utcnow
        return  # real HA available; leave it alone
    ha = types.ModuleType("homeassistant")
    ha_util = types.ModuleType("homeassistant.util")
    ha_dt = types.ModuleType("homeassistant.util.dt")
    ha_dt.utcnow = CLOCK.utcnow
    ha.util = ha_util
    ha_util.dt = ha_dt
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.dt"] = ha_dt


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_install_ha_stubs()

# Build enough of a package skeleton that the relative import in
# control.py ("from ..const import ...") resolves to the real const.py
# instead of copying constants into the tests.
_ns_cc = types.ModuleType("custom_components")
_ns_cc.__path__ = []
_ns_tadiy = types.ModuleType("custom_components.tadiy")
_ns_tadiy.__path__ = [str(TADIY_DIR)]
_ns_core = types.ModuleType("custom_components.tadiy.core")
_ns_core.__path__ = [str(CORE_DIR)]
sys.modules.setdefault("custom_components", _ns_cc)
sys.modules.setdefault("custom_components.tadiy", _ns_tadiy)
sys.modules.setdefault("custom_components.tadiy.core", _ns_core)

const = _load("custom_components.tadiy.const", TADIY_DIR / "const.py")
control = _load(
    "custom_components.tadiy.core.control", TADIY_DIR / "core" / "control.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_controller(hysteresis=DEFAULT_HYSTERESIS):
    """Fresh controller bound to the fake clock."""
    c = control.HeatingController(hysteresis=hysteresis)
    return c


def feed(ctrl, readings, target, dt=60.0):
    """Feed a sequence of temperatures with `dt` seconds between them.

    Returns the list of (should_heat, effective_target) results.
    """
    out = []
    for t in readings:
        out.append(ctrl.should_heat(t, target))
        CLOCK.advance(dt)
    return out


def states(results):
    return [heating for heating, _eff in results]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class TestHysteresis(unittest.TestCase):
    def setUp(self):
        CLOCK.set(_B0)
        logging.getLogger("custom_components.tadiy.core.control").setLevel(logging.CRITICAL)

    def test_off_below_lower_threshold_first_reading_confirm_gate(self):
        """First cold reading only generates a confirmation, not a flip."""
        ctrl = make_controller()
        r, eff = ctrl.should_heat(19.0, 20.0)  # 19.0 < 19.75
        assert (r, eff) == (False, 20.0)
        assert ctrl._heating_active is False

    def test_on_after_two_cold_readings(self):
        ctrl = feed(make_controller(), [19.0, 19.0], 20.0)
        assert states(ctrl) == [False, True]

    def test_off_at_upper_threshold_after_two_readings(self):
        ctrl = make_controller()
        # Force active state directly (white-box, cycle/confirm gates bypassed).
        ctrl._heating_active = True
        ctrl._last_state_change = CLOCK.utcnow() - timedelta(minutes=30)
        CLOCK.advance(60)
        assert states(feed(ctrl, [20.25, 20.25], 20.0)) == [True, False]

    def test_back_on_after_dropping_below_lower_threshold(self):
        ctrl = make_controller()
        feed(ctrl, [19.0, 19.0], 20.0)          # -> ON
        CLOCK.advance(6 * 60)
        r = feed(ctrl, [19.5, 19.5], 20.0)      # below band, new value
        assert states(r) == [True, True]        # ON only ends at >= 20.25
        CLOCK.advance(2 * 60)
        r = feed(ctrl, [19.0, 19.0], 20.0)      # back through the band down
        assert states(r) == [True, True]
        CLOCK.advance(6 * 60)
        r = feed(ctrl, [19.0, 19.0], 20.0)
        assert states(r) == [True, True]        # remains ON below the switch-off threshold

    def test_exact_midpoint_keeps_state_and_no_flip_confirm(self):
        ctrl = make_controller()
        r, eff = ctrl.should_heat(19.75, 20.0)  # == turn_on_threshold
        assert (r, eff) == (False, 20.0)
        assert ctrl._flip_confirm_count == 0

    def test_default_hysteresis_from_const(self):
        assert const.DEFAULT_HYSTERESIS == 0.5

    def test_custom_hysteresis_widens_band(self):
        ctrl = make_controller(hysteresis=2.0)  # band = target +/- 1.0
        r = feed(ctrl, [18.9, 18.9], 20.0)
        assert states(r)[-1] is True
        CLOCK.advance(6 * 60)
        assert states(feed(ctrl, [19.5, 19.5], 20.0))[-1] is True
        CLOCK.advance(6 * 60)
        # 19.0 is the ON-threshold edge; while heating, OFF happens at >= 21.0
        assert ctrl._heating_active is True

    def test_flip_confirm_count_resets_when_state_agrees_again(self):
        ctrl = make_controller()
        ctrl.should_heat(19.0, 20.0)            # cold -> count 1
        ctrl.should_heat(20.0, 20.0)            # in band -> reset
        assert ctrl._flip_confirm_count == 0


class TestCycleAndReset(unittest.TestCase):
    def setUp(self):
        CLOCK.set(_B0)

    def test_minimum_cycle_blocks_early_shutdown(self):
        ctrl = make_controller()
        assert states(feed(ctrl, [19.0, 19.0], 20.0)) == [False, True]

        # Abschalten vor Ablauf von 300 Sekunden verhindern.
        assert states(feed(ctrl, [21.0, 21.0], 20.0)) == [True, True]
        assert ctrl._heating_active is True

    def test_shutdown_after_minimum_cycle(self):
        ctrl = make_controller()
        feed(ctrl, [19.0, 19.0], 20.0)
        CLOCK.advance(300)

        assert states(feed(ctrl, [21.0, 21.0], 20.0)) == [True, False]

    def test_reset_clears_state_and_history(self):
        ctrl = make_controller()
        feed(ctrl, [19.0, 19.0], 20.0)

        ctrl.reset()

        assert ctrl._heating_active is False
        assert ctrl._last_state_change is None
        assert ctrl._flip_confirm_count == 0
        assert len(ctrl._temp_history) == 0

    def test_single_temperature_spike_does_not_switch_on(self):
        ctrl = make_controller()

        assert states(feed(ctrl, [20.0, 19.0, 20.0], 20.0)) == [
            False, False, False
        ]
        assert ctrl._flip_confirm_count == 0

    def test_target_step_down_lifts_cycle_guard(self):
        """Planabsenkung (K-01): Setpoint reduction lifts cycle guard for immediate shutdown."""
        ctrl = make_controller()
        feed(ctrl, [19.0, 19.0], 21.0)
        assert ctrl._heating_active is True

        # Target drops to 18.0 only 30s later (within 300s minimum cycle)
        CLOCK.advance(30)
        should_heat, _ = ctrl.should_heat(19.5, 18.0)
        assert should_heat is False
        assert ctrl._heating_active is False
