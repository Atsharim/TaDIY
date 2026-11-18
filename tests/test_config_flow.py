"""Unit tests for TaDIY ConfigFlow (K-11)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
        vol.Schema = MagicMock(side_effect=lambda d: d)
        vol.Required = MagicMock(side_effect=lambda k, **kw: k)
        vol.Optional = MagicMock(side_effect=lambda k, **kw: k)
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

    if "homeassistant.data_entry_flow" not in sys.modules:
        ha_def = types.ModuleType("homeassistant.data_entry_flow")
        ha_def.FlowResult = dict
        sys.modules["homeassistant.data_entry_flow"] = ha_def
    else:
        ha_def = sys.modules["homeassistant.data_entry_flow"]
        ha_def.FlowResult = dict

    if "homeassistant.helpers" not in sys.modules:
        ha_hlp = types.ModuleType("homeassistant.helpers")
        ha_hlp.__path__ = []
        sys.modules["homeassistant.helpers"] = ha_hlp
    else:
        ha_hlp = sys.modules["homeassistant.helpers"]
        if not hasattr(ha_hlp, "__path__"):
            ha_hlp.__path__ = []

    if "homeassistant.helpers.entity_registry" not in sys.modules:
        ha_er = types.ModuleType("homeassistant.helpers.entity_registry")
        ha_er.async_get = MagicMock()
        sys.modules["homeassistant.helpers.entity_registry"] = ha_er
        ha_hlp.entity_registry = ha_er

    if "homeassistant.helpers.selector" not in sys.modules:
        ha_sel = types.ModuleType("homeassistant.helpers.selector")
        class TextSelector:
            def __init__(self, *a, **k): pass
        class EntitySelector:
            def __init__(self, *a, **k): pass
        class EntitySelectorConfig:
            def __init__(self, *a, **k): pass
        class NumberSelector:
            def __init__(self, *a, **k): pass
        class NumberSelectorConfig:
            def __init__(self, *a, **k): pass
        class NumberSelectorMode:
            BOX = "box"
            SLIDER = "slider"
        class SelectSelector:
            def __init__(self, *a, **k): pass
        class SelectSelectorConfig:
            def __init__(self, *a, **k): pass
        class SelectOptionDict:
            def __init__(self, *a, **k): pass
        ha_sel.TextSelector = TextSelector
        ha_sel.EntitySelector = EntitySelector
        ha_sel.EntitySelectorConfig = EntitySelectorConfig
        ha_sel.NumberSelector = NumberSelector
        ha_sel.NumberSelectorConfig = NumberSelectorConfig
        ha_sel.NumberSelectorMode = NumberSelectorMode
        ha_sel.SelectSelector = SelectSelector
        ha_sel.SelectSelectorConfig = SelectSelectorConfig
        ha_sel.SelectOptionDict = SelectOptionDict
        sys.modules["homeassistant.helpers.selector"] = ha_sel
        ha_hlp.selector = ha_sel

    if "homeassistant.util" not in sys.modules:
        ha_util = types.ModuleType("homeassistant.util")
        ha_util.__path__ = []
        sys.modules["homeassistant.util"] = ha_util
        ha.util = ha_util

    if "homeassistant.util.dt" not in sys.modules:
        ha_dt = types.ModuleType("homeassistant.util.dt")
        def utcnow() -> datetime:
            return datetime.now(timezone.utc)
        def now() -> datetime:
            return datetime.now(timezone.utc)
        ha_dt.utcnow = utcnow
        ha_dt.now = now
        sys.modules["homeassistant.util.dt"] = ha_dt
        ha_util.dt = ha_dt

    if "homeassistant.config_entries" not in sys.modules:
        ha_cfg = types.ModuleType("homeassistant.config_entries")
        sys.modules["homeassistant.config_entries"] = ha_cfg
    else:
        ha_cfg = sys.modules["homeassistant.config_entries"]

    class ConfigEntry:
        def __init__(self, entry_id="test_entry", data=None):
            self.entry_id = entry_id
            self.data = data or {}

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain

        async def async_set_unique_id(self, unique_id, raise_on_progress=True):
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            pass

        def async_create_entry(self, title, data):
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(self, step_id, data_schema=None, errors=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}

        def async_abort(self, reason):
            return {"type": "abort", "reason": reason}

    class OptionsFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)

    ha_cfg.ConfigEntry = ConfigEntry
    ha_cfg.ConfigFlow = ConfigFlow
    ha_cfg.OptionsFlow = OptionsFlow

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

from custom_components.tadiy.config_flow import TaDIYConfigFlow
from custom_components.tadiy.const import CONF_HUB, CONF_ROOM_NAME, CONF_TRV_ENTITIES


class TestConfigFlow(unittest.TestCase):
    """Test Hub and Room ConfigFlow logic (K-11)."""

    def setUp(self):
        self.flow = TaDIYConfigFlow()
        self.hass = MagicMock()
        self.flow.hass = self.hass

    def test_first_run_creates_hub_automatically(self):
        """When no hub exists, async_step_user automatically creates the Hub entry."""
        self.hass.config_entries.async_entries.return_value = []

        result = asyncio.run(self.flow.async_step_user())

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "TaDIY Hub")
        self.assertTrue(result["data"][CONF_HUB])
        self.assertEqual(self.flow.unique_id, "tadiy_hub")

    def test_subsequent_run_prompts_for_room_setup(self):
        """When a hub already exists, async_step_user shows the room configuration form."""
        hub_entry = MagicMock()
        hub_entry.data = {CONF_HUB: True}
        self.hass.config_entries.async_entries.return_value = [hub_entry]

        result = asyncio.run(self.flow.async_step_user())

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "room")

    def test_room_creation_success(self):
        """Valid room input creates room entry linked to hub via hub_entry_id."""
        hub_entry = MagicMock()
        hub_entry.entry_id = "hub_123"
        hub_entry.data = {CONF_HUB: True}
        self.hass.config_entries.async_entries.return_value = [hub_entry]

        room_input = {
            CONF_ROOM_NAME: "Living Room",
            CONF_TRV_ENTITIES: ["climate.trv_radiator"],
        }

        result = asyncio.run(self.flow.async_step_room(room_input))

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Living Room")
        self.assertEqual(result["data"]["hub_entry_id"], "hub_123")
        self.assertEqual(result["data"][CONF_TRV_ENTITIES], ["climate.trv_radiator"])
        self.assertTrue(self.flow.unique_id.startswith("tadiy_room_"))

    def test_duplicate_room_name_rejected(self):
        """Room with existing name is rejected with room_already_exists error."""
        hub_entry = MagicMock()
        hub_entry.entry_id = "hub_123"
        hub_entry.data = {CONF_HUB: True}

        existing_room = MagicMock()
        existing_room.data = {CONF_ROOM_NAME: "Living Room", CONF_HUB: False}
        self.hass.config_entries.async_entries.return_value = [hub_entry, existing_room]

        room_input = {
            CONF_ROOM_NAME: "Living Room",
            CONF_TRV_ENTITIES: ["climate.trv_2"],
        }

        result = asyncio.run(self.flow.async_step_room(room_input))

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "room")
        self.assertEqual(result["errors"]["base"], "room_already_exists")

    def test_room_creation_aborts_without_hub(self):
        """Room creation aborts with no_hub_found if hub was somehow deleted."""
        self.hass.config_entries.async_entries.return_value = []

        room_input = {
            CONF_ROOM_NAME: "Office",
            CONF_TRV_ENTITIES: ["climate.trv_office"],
        }

        result = asyncio.run(self.flow.async_step_room(room_input))

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "no_hub_found")


if __name__ == "__main__":
    unittest.main()
