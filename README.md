<p align="center">
  <img src="https://raw.githubusercontent.com/home-assistant/brands/master/custom_integrations/tadiy/logo.png" alt="TaDIY Logo" width="350">
</p>

# TaDIY - Adaptive Climate Orchestrator for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-3.1.5-blue.svg)](https://github.com/Atsharim/TaDIY/releases/)
[![Tests](https://img.shields.io/badge/tests-69%20passing-brightgreen.svg)](https://github.com/Atsharim/TaDIY)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **⚠️ Disclaimer**: Personal hobby/learning project. Provided as-is. Use at your own risk.

TaDIY is an adaptive smart heating integration for Home Assistant inspired by Tado. It coordinates thermostatic radiator valves (TRVs), external room sensors, and boiler/relay controls to provide comfortable room temperatures, prevent oscillation/overshoot, track energy savings, and safeguard your heating equipment.

---

## 🌟 Key Features in v3.1

### Core Control & Anti-Hysteresis
- **🎯 Dynamic Anti-Hysteresis & Overshoot Learning**: Automatically learns heating inertia and cuts off before reaching setpoint to prevent temperature overshoots.
- **🔄 Instant Setpoint Drop Response**: Immediate valve shutoff on schedule reduction without waiting for cycle guard expiration.
- **🌡️ Multi-Sensor Fusion & Automatic Fallback**: Combines external temperature sensors with TRV sensors. Automatically falls back to internal TRV sensors if external sensors go offline.
- **🛡️ Störungsüberwachung (Safety & Fault Monitoring)**: Detects heating failure (boiler failure / stuck closed valve) and overheating (stuck open valve / calcification).
- **Intelligent Window Detection**: Dual-stage detection via physical contact sensors (`window_sensors`) or rapid temperature drop (fallback). Exposed natively as `binary_sensor.<room>_window`.
- **💼 Homeoffice & Presence Automation**: Automatically tracks presence, provides persistent away overrides with grace periods, and handles homeoffice schedules with automatic after-work revert (`homeoffice_end_hour`, default 17:00).
- **🔧 TRV Calibration & Valve Protection**: Weekly valve exercise cycles against lime buildup; dynamic calibration offset disabled when room reaches idle state.

---

## 🏗️ Repository Architecture

```
TaDIY/
├── .forgejo/                 # Forgejo CI workflows
├── .github/                  # GitHub Actions CI workflows
├── .githooks/                # Pre-commit hooks for local verification
├── custom_components/tadiy/  # Home Assistant Integration
│   ├── core/                 # Decoupled control & calculation modules
│   │   ├── calibration.py    # TRV temperature calibration
│   │   ├── control.py        # Hysteresis controller & cycle guard
│   │   ├── early_start.py    # Heat-up model & preheat calculator
│   │   ├── orchestrator.py   # Central target & heating arbitrator
│   │   ├── overshoot.py      # Overshoot learning & anti-hysteresis
│   │   ├── room_coupling.py  # Heat transfer between adjacent rooms
│   │   ├── safety.py         # Equipment protection & stuck-valve detection
│   │   ├── sensor_manager.py # Sensor fusion, filtering & fallback
│   │   ├── valve_protection.py # Lime protection exercise cycles
│   │   ├── weather_predictor.py# Outdoor weather prediction & cold fronts
│   │   └── window.py         # Window timeout & state machine
│   ├── binary_sensor.py      # Binary sensors (heating problems, window status)
│   ├── climate.py            # TaDIY Room Climate entity
│   ├── coordinator.py        # Central DataUpdateCoordinator
│   ├── number.py             # Number inputs (boost duration, boost temp)
│   ├── select.py             # Mode selectors (away, override)
│   ├── sensor.py             # Sensors (heating rate, savings, comfort)
│   ├── www/                  # Frontend panel & Lovelace cards
│   ├── manifest.json         # Integration manifest (v3.1.5)
│   └── strings.json          # UI translations schema
├── docs/                     # Technical documentation & change logs
│   ├── AENDERUNGEN-2026-11.md# Milestone change log
│   └── STATUS.md             # Project status & open tasks
└── tests/                    # Automated unit tests (69 tests)
```

---

## 📦 Entities per Room

When a room is added, TaDIY registers a cohesive device with the following entities:

| Domain | Entity | Description |
|---|---|---|
| **climate** | `climate.<room>` | Main heating controller (HVAC mode, target temperature, comfort attributes) |
| **binary_sensor** | `binary_sensor.<room>_window` | Window open/closed status (Device Class: `window`) |
| **binary_sensor** | `binary_sensor.<room>_heating_problem` | Fault monitoring (Device Class: `problem`) |
| **sensor** | `sensor.<room>_window_state` | Detailed window timeout phase (open, grace, cooldown) |
| **sensor** | `sensor.<room>_heating_rate` | Learned heating rate in °C/h |
| **sensor** | `sensor.<room>_room_comfort` | Comfort score (0–100%) and comfort zone |
| **sensor** | `sensor.<room>_energy_savings_today` | Cumulative savings today (kWh and €) |
| **sensor** | `sensor.<room>_heating_time_today` | Total burner active time today |
| **number** | `number.<room>_boost_temperature` | Configurable boost setpoint |
| **number** | `number.<room>_boost_duration` | Configurable boost duration (minutes) |
| **button** | `button.<room>_boost_room` | Trigger manual room boost |
| **button** | `button.<room>_clear_override` | Return room to schedule immediately |

---

## ⚙️ Installation & Setup

### Via HACS (Recommended)
1. Open **HACS** → **Integrations** → **Custom repositories**.
2. Add repository URL `https://github.com/Atsharim/TaDIY` with category `Integration`.
3. Download and restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration** → **TaDIY**.

### Initial Configuration
- **First Run**: Automatically sets up the **TaDIY Hub** (managing global timeouts, away modes, and scheduling).
- **Subsequent Runs**: Prompts to configure **Rooms**:
  - Name, assigned TRV climate entities, main temperature sensor, optional window sensors, and humidity sensor.
  - If no external temperature sensor is available, the internal TRV sensor is used automatically.

---

## 🧪 Testing & Quality Assurance

The codebase includes an isolated test suite running in <0.1s without external dependencies:

```bash
# Run unit tests locally
python -m unittest discover -s tests -v

# Verify JSON syntax
python -m json.tool hacs.json > /dev/null
python -m json.tool custom_components/tadiy/manifest.json > /dev/null
```

All pushes and pull requests are validated via:
- **Forgejo CI** (`.forgejo/workflows/test.yaml`)
- **GitHub Actions** (`.github/workflows/validate.yaml`)
- **Local Pre-Commit Hook** (`.githooks/pre-commit`)

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
