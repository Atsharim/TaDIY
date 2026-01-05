# TaDIY — Adaptive Climate Orchestrator

TaDIY is a personal Home Assistant integration designed to manage heating (TRVs) with a logic and feel inspired by Tado.

## Project Goal

The main goal of this project is to create a simple, local, and DIY heating controller for my own Home Assistant setup. I am a beginner in programming, so this is a "learning by doing" project.

I am sharing this in case others find it useful or want to help improve the logic.

## Current Status

- **In Development:** Features are added when I need them for my own home.
- **Maintenance:** Updates might be frequent or there might be no changes for months.
- **Focus:** Simple TRV management and Tado-like scheduling.

## Installation

### Via HACS (Recommended)

1. Add this repository as a custom repository in HACS:
   - HACS → Integrations → ⋮ → Custom Repositories
   - URL: `https://github.com/Atsharim/TaDIY`
   - Category: Integration
2. Search for "TaDIY" in HACS and install
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services → Add Integration → TaDIY

### Manual Installation

1. Copy the `custom_components/tadiy` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Add Integration → TaDIY

## Disclaimer

This is a private hobby project. Use it at your own risk. Since I am still learning, the code is simple and might change significantly over time. Feedback and contributions are welcome but please don't expect professional support.

---

**Inspired by Tado, built for Home Assistant.**
