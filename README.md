# TaDIY - Tado DIY Smart Heating for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/Atsharim/TaDIY.svg)](https://GitHub.com/Atsharim/TaDIY/releases/)
[![License](https://img.shields.io/github/license/Atsharim/TaDIY.svg)](https://github.com/Atsharim/TaDIY/blob/main/LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Atsharim/TaDIY/graphs/commit-activity)

> **⚠️ DISCLAIMER**: This is a personal hobby/learning project and work in progress. I created this because I couldn't find an existing solution that met my requirements. **Use at your own risk. I am not liable for any damages, energy costs, or issues that may arise from using this integration.**

Transform your basic thermostatic radiator valves (TRVs) into a Tado-inspired smart heating system with advanced features like room comfort monitoring, energy savings tracking, intelligent scheduling, and multi-room coordination.

---

## 🌟 Features

### Core Heating Control
- **🎯 Smart Temperature Management**: Advanced PID control with optional heating curves
- **🏠 Multi-Room Support**: Coordinate heating across multiple rooms with room coupling
- **⏰ Flexible Scheduling**: Create custom heating schedules per room with visual editor
- **📍 Location-Based Heating**: Automatically reduce heating when nobody is home
- **🪟 Window Detection**: Stop heating when windows are open (sensor-based or temperature-drop detection)
- **🔧 TRV Calibration**: Automatic or manual calibration using room temperature sensors
- **🌡️ Sensor Fusion**: Combine multiple temperature sensors for accurate room temperature
- **🛡️ Safety Features**: Overheat protection, frost protection, valve protection cycles
- **📊 Learning Capabilities**: Learns heating rates, thermal mass, and optimal early start times

### Room Comfort Monitoring
- **📈 Comfort Score**: Real-time comfort scoring (0-100%) based on temperature and humidity
- **🎨 Visual Indicators**: Color-coded comfort levels (Optimal, Good, Acceptable, Too Warm/Cold/Dry/Humid)
- **📊 XY Comfort Diagram**: Tado-inspired 2D visualization of comfort zones
- **🌡️ Refined Scoring**: Fine-grained comfort assessment with multiple zones

### Energy Savings Tracking (Energy Savings)
- **⚡ Automatic Tracking**: Monitors energy savings from:
  - 🪟 Window open detection (prevented heating time)
  - 🚶 Away mode (reduced heating when nobody home)
  - ☀️ Warm weather (prevented heating due to outdoor temperature)
- **💰 Cost Calculation**: Estimates savings in kWh and € (configurable energy price)
- **📊 Historical Data**: Daily, weekly, and monthly savings statistics
- **📈 Visual Reports**: Energy Savings cards with breakdown by category

### User Interface
- **🎨 Modern Panel**: Tabbed panel interface with:
  - Overview (hub status, all rooms at a glance)
  - Scheduler (schedule management, coming soon)
  - Comfort (all room comfort XY diagrams)
  - Energy Savings (total savings and per-room breakdown)
- **🃏 Custom Lovelace Cards**:
  - Room Comfort Card (circular design)
  - Room Comfort XY Card (2D comfort field)
  - Energy Savings Card (savings visualization)
  - Schedule Editor Card
  - Overview Card

---

## 📸 Screenshots

<!-- TODO: Add screenshots here -->

---

## 📦 Installation

### Option A: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click on **Integrations**
3. Click the **3 dots** (⋮) in the top right → **Custom repositories**
4. Add repository:
   - URL: `https://github.com/Atsharim/TaDIY`
   - Category: `Integration`
5. Click **Download**
6. Restart Home Assistant
7. Go to **Settings** → **Devices & Services** → **Add Integration**
8. Search for "TaDIY" and follow the setup wizard

### Option B: Manual Installation

1. Download the [latest release](https://github.com/Atsharim/TaDIY/releases)
2. Extract the `custom_components/tadiy` folder
3. Copy to your Home Assistant `custom_components` directory:
   ```
   <config>/custom_components/tadiy/
   ```
4. Restart Home Assistant
5. Go to **Settings** → **Devices & Services** → **Add Integration**
6. Search for "TaDIY"

---

## ⚙️ Configuration

### Step 1: Create a Hub

The Hub manages global settings and coordinates all rooms.

1. Add the **TaDIY** integration
2. Select **Hub** as entry type
3. Configure:
   - **Name**: e.g., "TaDIY Hub"
   - **Default Mode**: Normal / Eco / Away / Off
   - **Frost Protection Temperature**: Minimum temperature (default: 5°C)
   - **Global Settings**:
     - Window open/close timeouts
     - Override timeout behavior
     - Early start settings
     - Learning enabled/disabled

### Step 2: Add Rooms

Add one room entry for each room/zone you want to control.

1. Add another **TaDIY** integration entry
2. Select **Room** as entry type
3. Configure:
   - **Room Name**: e.g., "Living Room"
   - **TRV Entities**: Select one or more climate entities (TRVs)
   - **Temperature Sensor**: Main room temperature sensor (required)
   - **Humidity Sensor**: Optional, enables comfort monitoring
   - **Window Sensors**: Optional, for window detection
   - **Outdoor Temperature Sensor**: Optional, for weather-based optimization
   - **Heating Curve**: Enable/disable heating curve based on outdoor temperature
   - **PID Control**: Enable/disable PID controller (advanced)
   - **Room Coupling**: Configure heat transfer from adjacent rooms

### Step 3: Register Custom Cards

**Option A: Via UI** (recommended)
1. Go to **Settings** → **Dashboards** → **Resources** (⋮ top right)
2. Click **+ Add Resource**
3. Add each card:

```
URL: /tadiy/tadiy-room-comfort-card.js
Type: JavaScript Module

URL: /tadiy/tadiy-room-comfort-xy-card.js
Type: JavaScript Module

URL: /tadiy/tadiy-energy-card.js
Type: JavaScript Module

URL: /tadiy/tadiy-schedule-card.js
Type: JavaScript Module

URL: /tadiy/tadiy-overview-card.js
Type: JavaScript Module
```

> **Note**: Each card requires a separate JS file. There is no "single import" option, as this is the standard Home Assistant approach.

**Option B: Via configuration.yaml**
```yaml
lovelace:
  mode: storage
  resources:
    - url: /tadiy/tadiy-room-comfort-card.js
      type: module
    - url: /tadiy/tadiy-room-comfort-xy-card.js
      type: module
    - url: /tadiy/tadiy-energy-card.js
      type: module
    - url: /tadiy/tadiy-schedule-card.js
      type: module
    - url: /tadiy/tadiy-overview-card.js
      type: module
```

---

## 🎯 Usage

### Panels

After installation, you'll find the **TaDIY panel** in the sidebar with multiple tabs:

- **🏠 Overview**: Hub status, all rooms at a glance
- **⏰ Scheduler**: Schedule management (configure via Hub settings)
- **🌡️ Comfort**: All room comfort XY diagrams
- **⚡ Energy Savings**: Total savings and breakdown

### Custom Cards

#### 1. Room Comfort Card (Circular)
```yaml
type: custom:tadiy-room-comfort-card
entity: sensor.ta_living_room_room_comfort
name: Living Room
show_score: true  # Show comfort score in center (default: true)
```

#### 2. Room Comfort XY Card (2D Diagram)
```yaml
type: custom:tadiy-room-comfort-xy-card
entity: sensor.ta_living_room_room_comfort
name: Living Room
show_score: true  # Show score below diagram (default: true)
temp_range: [19, 22]  # Temperature range for X-axis (optional)
humidity_range: [40, 60]  # Humidity range for Y-axis (optional)
```

**Features**:
- 2D comfort field (X: temperature, Y: humidity)
- Optimal zone highlighted in green
- Current state as animated dot
- Configurable axis ranges

#### 3. Energy Savings Card
```yaml
type: custom:tadiy-energy-card
entity: sensor.ta_living_room_energy_savings_today
name: Living Room
period: today  # today / week / month / last_30_days
show_breakdown: true  # Show category breakdown (default: true)
```

**Features**:
- Displays energy savings in kWh and €
- Breakdown by category (🪟 Window / 🚶 Away / ☀️ Weather)
- Switchable periods:
  - **today**: Current day
  - **week**: Current calendar week (Mon-Sun)
  - **month**: Current calendar month
  - **last_30_days**: Rolling 30-day window

#### 4. Schedule Card
```yaml
type: custom:tadiy-schedule-card
entity: climate.ta_living_room
```

**Features**:
- Visual schedule editor
- Multiple schedules per room
- Drag-and-drop time blocks
- Temperature presets

#### 5. Overview Card
```yaml
type: custom:tadiy-overview-card
```

**Features**:
- All rooms in one card
- Hub mode switcher
- Quick access to room details

### Example Dashboards

#### Minimal (Single Room)
```yaml
type: vertical-stack
cards:
  - type: custom:tadiy-room-comfort-xy-card
    entity: sensor.ta_living_room_room_comfort
    show_score: true

  - type: custom:tadiy-energy-card
    entity: sensor.ta_living_room_energy_savings_today
    period: today
    show_breakdown: true

  - type: entities
    title: Heating Control
    entities:
      - entity: climate.ta_living_room
      - entity: sensor.ta_living_room_heating_rate
        name: Heating Rate
      - entity: sensor.ta_living_room_heating_time_today
        name: Heating Time Today
```

#### Multi-Room Dashboard
```yaml
type: horizontal-stack
cards:
  # Living Room
  - type: vertical-stack
    cards:
      - type: custom:tadiy-room-comfort-xy-card
        entity: sensor.ta_living_room_room_comfort
        name: Living Room
      - type: custom:tadiy-energy-card
        entity: sensor.ta_living_room_energy_savings_today
        period: today
        show_breakdown: false

  # Bedroom
  - type: vertical-stack
    cards:
      - type: custom:tadiy-room-comfort-xy-card
        entity: sensor.ta_bedroom_room_comfort
        name: Bedroom
      - type: custom:tadiy-energy-card
        entity: sensor.ta_bedroom_energy_savings_today
        period: today
        show_breakdown: false
```

---

## 🔧 Advanced Configuration

### Energy Savings Settings

The Energy Savings sensor calculates savings based on:
- **Heating Power**: Default 2.0 kW (average per room)
- **Energy Price**: Default 0.30 €/kWh

These values can be customized per room via the room configuration attributes:
- `heating_power_kw`: Heating power in kilowatts
- `energy_price`: Energy price in € per kWh

> **Note**: Configuration via UI options flow is planned for a future release.

### Comfort Scoring Zones

| Zone | Temperature | Humidity | Score |
|------|-------------|----------|-------|
| **Perfect** | 21°C ± 0.5°C | 50% ± 2.5% | 100% |
| **Good** | 20-22°C | 45-55% | 85-99% |
| **Acceptable** | 19-23°C | 40-60% | 60-84% |
| **Poor** | Outside | Outside | <60% |

---

## 🐛 Troubleshooting

### Attributes not showing in UI

If room comfort or heating rate attributes are not visible in the More Info dialog:
1. Check **Developer Tools** → **States** to verify attributes exist
2. Clear browser cache (Ctrl+Shift+R)
3. Restart Home Assistant
4. Check Home Assistant logs for errors

### Energy Savings showing 0

Energy Savings tracking starts from installation. It needs time to accumulate data:
- **First day**: May show little or no savings
- **After 24h**: Should show meaningful data
- Historical data before installation is not available

### Custom Cards not loading

1. Verify cards are registered in **Resources**
2. Check browser console for JavaScript errors (F12)
3. Clear browser cache
4. Verify URLs are correct (`/tadiy/...`)

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.tadiy: debug
```

Then check **Settings** → **System** → **Logs**

---

## 🤝 Contributing

Contributions are welcome! This is a learning project, so feel free to:
- Report bugs via [GitHub Issues](https://github.com/Atsharim/TaDIY/issues)
- Suggest features or improvements
- Submit pull requests
- Share your dashboards and use cases

### Development

For developers:
1. Clone the repository
2. Make changes in `custom_components/tadiy/`
3. Test thoroughly in a development Home Assistant instance
4. Submit a pull request

---

## 📋 Supported Devices

TaDIY should work with **any TRV that is integrated into Home Assistant** as a `climate` entity, including:
- Zigbee TRVs (via Zigbee2MQTT, ZHA, deCONZ)
- Z-Wave TRVs (via Z-Wave JS)
- Other protocols (WiFi, Thread, Matter, etc.)

**Tested with**:
- Zigbee TRVs (various manufacturers)
- Temperature sensors (Zigbee, Aqara, Sonoff, etc.)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer (Again)

**This is a personal hobby project created for learning purposes.** I am not a professional developer, and this integration is provided "as-is" without any warranties or guarantees.

**Use at your own risk. I am not liable for:**
- Damage to your heating system or property
- Energy costs or excessive heating bills
- Lost data or Home Assistant issues
- Any other consequences of using this integration

Always monitor your heating system carefully and have backup heating controls in place.

---

## 💬 Support

For questions, issues, or discussions:
- [GitHub Issues](https://github.com/Atsharim/TaDIY/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/Atsharim/TaDIY/discussions) - General questions and community

---

## 🙏 Acknowledgments

- Home Assistant team for the amazing platform
- HACS for making custom integrations accessible
- The Home Assistant community for inspiration and support
- Tado for the design inspiration

---

**Made with ❤️ for the Home Assistant community**

**⭐ If you find this useful, please star the repository!**
