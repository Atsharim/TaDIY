# TaDIY - Adaptive Climate Orchestrator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Atsharim/TaDIY.svg)](https://github.com/Atsharim/TaDIY/releases)
[![License](https://img.shields.io/github/license/Atsharim/TaDIY.svg)](LICENSE)

**TaDIY** (Take a DIY) is an advanced, adaptive climate control integration for Home Assistant. It provides intelligent heating orchestration with learning capabilities, schedule management, and multi-room coordination.

## Features

- **Adaptive Learning**: Learns heating patterns and optimizes early-start times
- **Multi-Room Support**: Coordinate heating across multiple rooms
- **Smart Scheduling**: Per-room and hub-wide schedule management
- **Window Detection**: Automatic temperature adjustments when windows are opened
- **Multiple Operating Modes**: Normal, Home Office, Vacation, Party modes
- **Boost Function**: Quick temperature boost for all rooms
- **TRV Integration**: Works with any Home Assistant compatible thermostatic radiator valves

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add the URL `https://github.com/Atsharim/TaDIY` with category "Integration"
6. Click "Install" on the TaDIY card
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Extract the `tadiy` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **TaDIY**
4. Follow the setup wizard:
   - First, create a **Hub** (central coordinator)
   - Then, add **Rooms** linked to the hub

### Hub Configuration

The Hub is the central coordinator that manages:
- Global heating modes
- Learning data across all rooms
- Hub-wide schedules
- Cross-room coordination

Required settings:
- **Name**: A friendly name for your hub
- **Scan Interval**: How often to update (default: 60 seconds)

### Room Configuration

Each room requires:
- **Room Name**: Unique identifier
- **TRV Entities**: One or more climate entities (thermostatic radiator valves)
- **Temperature Sensor** (optional): External temperature sensor for better accuracy
- **Window Sensors** (optional): Binary sensors to detect open windows

Advanced settings:
- **Window Open Temperature**: Target temperature when window is detected as open
- **Early Start**: Enable adaptive learning for optimal heating start times
- **Heating Curve**: Adjust heating behavior based on outdoor temperature

## Usage

### Operating Modes

- **Normal**: Standard scheduled heating
- **Home Office**: Extended daytime heating schedule
- **Vacation**: Reduced heating to save energy
- **Party**: Boost mode for social gatherings

### Services

TaDIY provides several services for automation:

#### `tadiy.force_refresh`
Force an immediate data refresh from all devices.

```yaml
service: tadiy.force_refresh
```

#### `tadiy.reset_learning`
Reset learning data for all rooms or a specific room.

```yaml
service: tadiy.reset_learning
data:
  room: "Living Room"  # Optional, omit to reset all rooms
```

#### `tadiy.boost_all_rooms`
Quickly boost temperature in all rooms.

```yaml
service: tadiy.boost_all_rooms
data:
  temperature: 23  # Optional, default: 23°C
  duration_minutes: 60  # Optional, default: 60 minutes
```

#### `tadiy.set_hub_mode`
Change the hub operating mode.

```yaml
service: tadiy.set_hub_mode
data:
  mode: "homeoffice"  # Options: normal, homeoffice, vacation, party
```

### Entities

For each room, TaDIY creates:

- **Climate Entity**: Main thermostat control
- **Sensors**: Temperature, humidity, valve position, battery levels
- **Buttons**: Force refresh, reset learning
- **Selects**: Mode selection, schedule selection
- **Numbers**: Temperature setpoints, timing adjustments

## Advanced Features

### Adaptive Learning

TaDIY learns how long your rooms take to heat up and automatically starts heating earlier to reach the target temperature at the scheduled time. The learning improves over time and adapts to:
- Room thermal mass
- Outside temperature
- Heating system capacity
- Insulation quality

### Schedule Management

Create flexible heating schedules with:
- Multiple setpoints per day
- Different schedules for weekdays/weekends
- Per-room or hub-wide schedules
- Easy import/export via YAML

### Window Detection

When configured window sensors detect an open window:
- Temperature automatically reduces to prevent energy waste
- Heating resumes when windows are closed
- Configurable threshold temperatures

## Troubleshooting

### Rooms not appearing

Ensure the Hub is set up first before adding rooms. Rooms require an active Hub coordinator.

### Learning not working

1. Check that "Early Start" is enabled in room options
2. Verify schedules are active
3. Allow 2-3 weeks for initial learning
4. Use `tadiy.reset_learning` to start fresh if needed

### TRV not responding

1. Verify TRV entity IDs are correct
2. Check that TRVs are reachable in Home Assistant
3. Ensure TRVs support temperature setting (check integration documentation)

## Support

- **Issues**: [GitHub Issues](https://github.com/Atsharim/TaDIY/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Atsharim/TaDIY/discussions)
- **Documentation**: [Wiki](https://github.com/Atsharim/TaDIY/wiki)

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

Developed by [@Atsharim](https://github.com/Atsharim)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.
