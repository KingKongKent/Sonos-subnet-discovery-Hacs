# Agent Instructions

## Project Overview
This is the **Sonos Subnet Discovery** HACS integration for Home Assistant. It enables discovery and control of Sonos speakers on different subnets/VLANs than where Home Assistant is installed, solving the multicast discovery limitation.

## Key Features
- Manual IP address entry for Sonos speakers
- Subnet scanning to discover Sonos devices on remote networks
- Direct HTTP/UPnP communication (no multicast dependency)
- Full media player controls (play, pause, volume, track navigation)

## Development Guidelines

### Code Style
- Follow Python best practices and PEP 8 style guidelines
- Use type hints for function parameters and return values
- Use async/await patterns for all I/O operations
- Write clear, descriptive docstrings for classes and functions

### Home Assistant Integration Standards
- Follow Home Assistant's integration development guidelines
- Use `CoordinatorEntity` for entities that need periodic updates
- Implement proper error handling with logging
- Use config flow for user configuration

### Testing
- Write unit tests for new functionality
- Test against real Sonos hardware when possible
- Ensure existing tests pass before submitting changes

### Documentation
- Update README.md for user-facing changes
- Document configuration options and usage examples
- Update strings.json and translations for UI text

## File Structure
```
custom_components/sonos_subnet/
├── __init__.py          # Integration setup and services
├── manifest.json        # Integration metadata
├── const.py             # Constants and configuration keys
├── config_flow.py       # UI configuration flow
├── coordinator.py       # DataUpdateCoordinator for state management
├── discovery.py         # Sonos device discovery utilities
├── media_player.py      # Media player entity
├── services.yaml        # Service definitions
├── strings.json         # UI strings
└── translations/
    └── en.json          # English translations
```

## Common Tasks
- **Adding a new entity**: Create entity class in appropriate platform file, update PLATFORMS in `__init__.py`
- **Adding configuration options**: Update `config_flow.py`, `const.py`, and `strings.json`
- **Adding a new service**: Define in `services.yaml`, implement handler in `__init__.py`
- **Debugging**: Enable debug logging with `logger.logs.custom_components.sonos_subnet: debug`

## Sonos Communication
- Sonos HTTP API runs on port 1400
- Device info available at `/xml/device_description.xml`
- UPnP SOAP commands for transport and rendering control
- All communication is HTTP-based, no SSDP/multicast required
