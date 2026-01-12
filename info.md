# TaDIY - Adaptive Climate Orchestrator

**TaDIY** (Take a DIY) brings intelligent, adaptive climate control to your Home Assistant installation.

## Key Features

### Adaptive Learning
TaDIY learns how your rooms heat up over time and automatically adjusts when to start heating to reach your desired temperature at exactly the right time.

### Multi-Room Coordination
Create a central Hub that coordinates heating across all your rooms, ensuring optimal comfort and energy efficiency throughout your home.

### Flexible Scheduling
Set up different heating schedules for:
- Normal weekdays
- Weekends
- Home office days
- Vacation periods
- Party mode

### Smart Window Detection
Automatically reduce heating when windows are opened and resume when closed, saving energy without manual intervention.

## Quick Start

1. **Install via HACS**
   - Add this repository as a custom repository in HACS
   - Install TaDIY integration
   - Restart Home Assistant

2. **Configure Hub**
   - Go to Settings → Devices & Services
   - Add TaDIY integration
   - Create a Hub (central coordinator)

3. **Add Rooms**
   - Add TaDIY integration again for each room
   - Link to your TRV entities
   - Configure optional temperature and window sensors

4. **Enjoy**
   - Let TaDIY learn your heating patterns
   - Adjust schedules to your lifestyle
   - Save energy automatically

## Requirements

- Home Assistant 2024.1.0 or later
- Compatible thermostatic radiator valves (TRVs)
- Optional: Temperature sensors for better accuracy
- Optional: Window/door sensors for automatic detection

## Support

Need help? Check out:
- [Documentation](https://github.com/Atsharim/TaDIY)
- [Issue Tracker](https://github.com/Atsharim/TaDIY/issues)
- [Discussions](https://github.com/Atsharim/TaDIY/discussions)
