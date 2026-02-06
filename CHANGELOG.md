# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-02-06

### 🎉 Major Features Added
- **Native Home Assistant Grouping** - Full support for speaker grouping directly in Home Assistant UI
  - Click "⋮" menu → "Group with" to select speakers
  - Bidirectional sync with Sonos app (groups made in either app sync automatically)
  - Visual indication of group members in speaker cards
  - Works exactly like the official Sonos integration

### ✨ Enhancements
- **Improved Metadata Handling**
  - Enhanced streaming radio support (TuneIn, Spotify Radio, etc.)
  - Better album artwork extraction with multiple fallback sources
  - Proper handling of live radio station names and current song info
  - Extracts `r:streamContent` and `r:radioShowMd` for streaming services
  
- **Group Detection**
  - Real-time zone group topology monitoring
  - Proper coordinator/member role identification
  - Entity ID to IP address conversion for seamless HA integration
  - Debug logging for troubleshooting grouping issues

- **Services Enhanced**
  - `sonos_subnet.join` - Now accepts both entity_id and IP address
  - `sonos_subnet.unjoin` - Now accepts both entity_id and IP address
  - Entity selector UI for easier service calls

### 🐛 Bug Fixes
- Fixed metadata parsing for DIDL-Lite content
- Improved XML entity unescaping in zone group state
- Better error handling for streaming services without metadata
- Fixed fallback when track titles are unavailable

### 📚 Documentation
- Updated README with native grouping instructions
- Added visual guide for using grouping in UI
- Documented entity-based service calls
- Added troubleshooting section for grouping

## [1.0.1] - Previous Release

### Initial Features
- Manual IP address entry for Sonos speakers
- Subnet scanning for device discovery
- Basic media player controls (play, pause, volume, etc.)
- EQ controls (bass, treble, balance)
- Switch entities (crossfade, loudness, status light, etc.)
- Sleep timer services

