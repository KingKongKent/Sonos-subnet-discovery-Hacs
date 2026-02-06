# Sonos Subnet Discovery

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/KingKongKent/Sonos-subnet-discovery-Hacs)](https://github.com/KingKongKent/Sonos-subnet-discovery-Hacs/releases/latest)
[![GitHub](https://img.shields.io/github/license/KingKongKent/Sonos-subnet-discovery-Hacs)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/KingKongKent/Sonos-subnet-discovery-Hacs)](https://github.com/KingKongKent/Sonos-subnet-discovery-Hacs/issues)

A Home Assistant custom integration for discovering and controlling Sonos speakers on **different subnets** than your Home Assistant installation.

> **🎉 Version 1.1.0** - Now with **native Home Assistant grouping** that syncs with the Sonos app!

## Why This Integration?

The built-in Sonos integration in Home Assistant relies on **multicast/SSDP discovery**, which doesn't work across different subnets or VLANs. This integration solves that problem by:

- ✅ Allowing **manual IP address entry** for Sonos speakers
- ✅ Providing **subnet scanning** to discover Sonos devices on remote networks
- ✅ Using **direct HTTP/UPnP communication** instead of multicast discovery

## Features

### Media Player Controls
| Feature | Description |
|---------|-------------|
| ▶️ Play/Pause/Stop | Basic transport controls |
| 🔊 Volume | Set level, mute, step up/down |
| ⏭️ Track Control | Next/Previous track |
| 🔀 Shuffle | Toggle shuffle mode |
| 🔁 Repeat | Off, All, One modes |
| 🎵 Now Playing | Track title, artist, album, artwork |
| ⏱️ Seek | Jump to position in track |
| 🎶 Play Media | Play audio URLs directly |
| 🗑️ Clear Queue | Remove all tracks from queue |
| 👥 Speaker Grouping | Native HA grouping (like Sonos app) |

> ⚠️ **Known Issue:** The volume slider in the media player card does not work. Use the volume service call or automations instead.

### Sound Settings (Number Entities)
| Entity | Range | Description |
|--------|-------|-------------|
| 🎚️ Bass | -10 to +10 | Bass adjustment |
| 🎚️ Treble | -10 to +10 | Treble adjustment |
| ⚖️ Balance | -100 to +100 | Left/Right balance |

### Switches
| Entity | Description |
|--------|-------------|
| 🔀 Crossfade | Crossfade between tracks |
| 🔊 Loudness | Loudness compensation |
| 💡 Status Light | Speaker LED on/off |
| 👆 Touch Controls | Enable/disable physical buttons |
| 🌙 Night Mode | Reduce bass at night (soundbars) |
| 🗣️ Speech Enhancement | Boost dialog clarity (soundbars) |

### Services
| Service | Description |
|---------|-------------|
| `sonos_subnet.scan_subnet` | Discover Sonos devices on a subnet |
| `sonos_subnet.add_speaker` | Add a speaker by IP address |
| `sonos_subnet.join` | Group speakers together |
| `sonos_subnet.unjoin` | Remove speaker from group |
| `sonos_subnet.set_sleep_timer` | Set sleep timer (1-7200 seconds) |
| `sonos_subnet.clear_sleep_timer` | Cancel sleep timer |

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **Integrations** → **⋮** (three dots menu) → **Custom repositories**
3. Add repository URL: `https://github.com/KingKongKent/Sonos-subnet-discovery-Hacs`
4. Select category: **Integration**
5. Click **Add**
6. Search for "Sonos" and install **Sonos (Subnet Discovery)**
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/KingKongKent/Sonos-subnet-discovery-Hacs/releases)
2. Extract and copy `custom_components/sonos_subnet` to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Sonos"
4. Choose your setup method:

#### Option 1: Manual IP Entry
Enter the IP addresses of your Sonos speakers (comma-separated):
```
192.168.2.100, 192.168.2.101, 192.168.2.102
```

#### Option 2: Subnet Scan
Enter the subnet where your Sonos speakers are located:
```
192.168.2.0/24
```
This will scan all 254 addresses and find Sonos devices automatically.

### Adding More Speakers Later

Go to the integration's options to:
- Add individual speakers by IP
- Scan additional subnets
- Remove speakers

## Network Requirements

For this integration to work, your Home Assistant server must be able to reach the Sonos speakers:

| Requirement | Details |
|-------------|---------|
| **Routing** | Proper routing between HA subnet and Sonos subnet |
| **Firewall** | Allow TCP port **1400** between subnets |
| **No NAT** | Speakers should be directly reachable |

### Example Network Setup
```
┌─────────────────────────────────────────────────────┐
│                    Router/Firewall                   │
│         (Enable routing, allow port 1400)           │
└────────────────┬─────────────────┬──────────────────┘
                 │                 │
    ┌────────────┴───┐    ┌───────┴────────────┐
    │  192.168.1.0/24│    │  192.168.2.0/24    │
    │                │    │                    │
    │ Home Assistant │    │  Sonos Speakers    │
    │ 192.168.1.100  │    │  192.168.2.x       │
    └────────────────┘    └────────────────────┘
```

## Service Examples

### Scan a Subnet
```yaml
service: sonos_subnet.scan_subnet
data:
  subnet: "192.168.2.0/24"
  timeout: 5
```

### Add a Speaker
```yaml
service: sonos_subnet.add_speaker
data:
  ip_address: "192.168.2.105"
```

### Group Speakers

**Using Native Home Assistant UI:**
1. Open any Sonos speaker card in Home Assistant
2. Click the **"⋮" menu** (three dots)
3. Select **"Group with"** 
4. Choose which speakers to add to the group
5. Done! Changes sync with Sonos app instantly

**Using Services (Entity-based - Recommended):**
```yaml
service: sonos_subnet.join
data:
  entity_id: media_player.bedroom      # Speaker to join
  master_entity_id: media_player.living_room  # Master/coordinator
```

**Using Services (IP-based - Legacy):**
```yaml
service: sonos_subnet.join
data:
  ip_address: "192.168.2.101"  # Speaker to join
  master: "192.168.2.100"       # Master speaker
```

### Ungroup Speaker

**Using Native Home Assistant UI:**
1. Open the grouped speaker card
2. Click **"⋮" menu**
3. Select **"Ungroup"**

**Using Services (Entity-based - Recommended):**
```yaml
service: sonos_subnet.unjoin
data:
  entity_id: media_player.bedroom
```

**Using Services (IP-based - Legacy):**
```yaml
service: sonos_subnet.unjoin
data:
  ip_address: "192.168.2.101"
```

> **💡 Tip:** Grouping changes made in the Sonos app will automatically sync to Home Assistant within 10 seconds!

### Set Sleep Timer (30 minutes)
```yaml
service: sonos_subnet.set_sleep_timer
data:
  ip_address: "192.168.2.100"
  sleep_time: 1800
```

### Play Audio URL
```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "http://example.com/audio.mp3"
```

## Troubleshooting

### Speakers Not Found
1. **Check connectivity:**
   ```bash
   ping 192.168.2.100
   curl http://192.168.2.100:1400/xml/device_description.xml
   ```
2. **Check firewall:** Port 1400 must be open between subnets
3. **Verify IP:** Confirm the IP in the Sonos app under speaker settings

### Speakers Show as Unavailable
- Verify network routing is bidirectional
- Try increasing the scan timeout
- Check if speaker is powered on

### Controls Not Working
1. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.sonos_subnet: debug
   ```
2. Check logs for UPnP errors
3. Ensure no firewall is blocking responses

## Compatibility

| Component | Requirement |
|-----------|-------------|
| Home Assistant | 2024.1.0 or newer |
| Sonos Speakers | S2 firmware (HTTP API support) |
| Network | TCP connectivity on port 1400 |

## Known Limitations

- ❌ Sonos S1 (legacy) speakers not supported
- ❌ Media browsing not implemented (use Sonos app)
- ❌ Alarm management not included
- ❌ Surround/Sub configuration not supported

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Sonos, Inc. Sonos is a trademark of Sonos, Inc.

---

## Support

**Found this useful?** Consider supporting the project:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/kingkongkent)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue.svg?logo=paypal)](https://www.paypal.com/paypalme/KingKongKent)
[![GitHub stars](https://img.shields.io/github/stars/KingKongKent/Sonos-subnet-discovery-Hacs?style=social)](https://github.com/KingKongKent/Sonos-subnet-discovery-Hacs)

⭐ Star the repository on GitHub!
