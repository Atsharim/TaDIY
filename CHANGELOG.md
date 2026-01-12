# Changelog

All notable changes to TaDIY will be documented in this file.

## [0.2.0] - 2026-01-12

### Changed - Major Restructuring

**Breaking Changes:**
- Users will need to delete and re-add the integration due to device structure changes
- Existing configurations will not be automatically migrated

**Code Structure:**
- Merged coordinator_hub.py and coordinator_room.py into single coordinator.py
- Moved models/ content to core/ directory
  - models/room.py → core/room.py
  - models/schedule.py → core/schedule_model.py
- Moved device_helpers.py to core/device_helpers.py
- Removed empty ui/ directory
- Entity platforms remain in root (Home Assistant convention)

**Device Hierarchy:**
- Hub now creates automatically without user input
- Rooms are linked to Hub via via_device (Battery Notes style)
- Rooms appear as sub-entries under Hub in device list
- Hub configuration moved to device entities (no config menu)

**Configuration Flow:**
- Hub creates automatically with default global settings
- Room configuration simplified to 5 basic fields only:
  - Room Name
  - TRV Entities
  - Main Temperature Sensor
  - Window Sensors
  - Outdoor Sensor
- Advanced settings now managed via device entities

**Options Flow:**
- Hub options menu removed (settings via entities)
- Room options simplified to basic configuration only
- Schedule and learning settings moved to future phases

**Fixes:**
- Fixed bug causing 2 devices to be created per entry
- Fixed "undefined" device creation
- Fixed room labels showing variable names instead of readable text
- Improved unique ID generation for rooms (timestamp-based)

## [0.1.9] - 2026-01-11

### Previous Release
- Initial HACS release with multi-room support
- Schedule management
- Learning capabilities
