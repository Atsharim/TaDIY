# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024

### Added
- HACS support with proper configuration files
- README.md with comprehensive documentation
- LICENSE file (MIT)
- `.gitignore` for better version control
- `set_heating_curve` service for manual heating rate configuration
- Proper service schemas and validation

### Fixed
- Type hint error in `device_helpers.py` (`any` -> `Any`)
- Hub coordinator access in `switch.py` (incorrect data structure references)
- Mode inconsistency between `services.yaml`, `const.py`, and `strings.json`
- Service registration and unloading for all services
- `CONF_HUB` constant usage throughout the codebase

### Changed
- Unified hub modes: `normal`, `homeoffice`, `vacation`, `party`
- Improved service definitions with proper parameter validation
- Enhanced error handling in service implementations

## [0.1.0] - Initial Release

### Added
- Initial TaDIY integration
- Multi-room climate control
- Adaptive learning for heating patterns
- Schedule management
- Window detection
- Multiple operating modes
- Hub and Room coordinator architecture
