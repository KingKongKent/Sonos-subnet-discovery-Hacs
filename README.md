# Sonos Subnet Discovery

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for discovering and controlling Sonos speakers on different subnets than your Home Assistant installation.

## Why This Integration?

The built-in Sonos integration in Home Assistant relies on multicast/SSDP discovery, which doesn't work across different subnets or VLANs. This integration solves that problem by:

- Allowing **manual IP address entry** for Sonos speakers
- Providing **subnet scanning** to discover Sonos devices on remote networks
- Using **direct HTTP/UPnP communication** instead of multicast discovery

## Features

- 🔍 **Subnet Scanning**: Scan entire subnets to find Sonos devices
- 📝 **Manual IP Entry**: Add speakers by IP address
- 🎵 **Full Media Player Support**: Play, pause, stop, volume control, track navigation
- 🔄 **Auto-refresh**: Automatic state updates from your speakers
- ➕ **Dynamic Device Management**: Add or remove speakers without reconfiguration
- 🏠 **Multi-subnet Support**: Works across VLANs and different network segments

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots menu (⋮) in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/your-username/sonos-subnet-hacs`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Sonos Subnet Discovery" and install it
9. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/sonos_subnet` folder from this repository
2. Copy it to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Sonos Subnet Discovery"
4. Choose your setup method:
   - **Manual**: Enter IP addresses of your Sonos speakers (comma-separated)
   - **Scan**: Enter a subnet in CIDR notation to scan for devices

### Manual IP Entry

Enter the IP addresses of your Sonos speakers separated by commas:

```
192.168.2.100, 192.168.2.101, 192.168.2.102
```

### Subnet Scanning

Enter the subnet where your Sonos speakers are located:

```
192.168.2.0/24
```

This will scan all 254 addresses in the subnet and find Sonos devices.

## Network Requirements

For this integration to work, your Home Assistant server must be able to reach the Sonos speakers over the network. This typically requires:

1. **Routing**: Proper routing between your Home Assistant subnet and the Sonos subnet
2. **Firewall Rules**: Allow traffic on port 1400 (Sonos HTTP/UPnP port)
3. **No NAT**: Sonos speakers should be directly reachable (not behind NAT)

### Example Network Setup

```
Home Assistant:     192.168.1.100 (Subnet: 192.168.1.0/24)
Sonos Speakers:     192.168.2.x   (Subnet: 192.168.2.0/24)
Router/Firewall:    Enable routing between subnets, allow port 1400
```

## Services

The integration provides two services for managing speakers:

### `sonos_subnet.scan_subnet`

Scan a subnet for Sonos devices.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subnet` | string | Yes | Subnet in CIDR notation (e.g., `192.168.2.0/24`) |
| `timeout` | integer | No | Timeout per device in seconds (default: 5) |

**Example:**
```yaml
service: sonos_subnet.scan_subnet
data:
  subnet: "192.168.2.0/24"
  timeout: 5
```

### `sonos_subnet.add_speaker`

Add a Sonos speaker by IP address.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ip_address` | string | Yes | IP address of the Sonos speaker |

**Example:**
```yaml
service: sonos_subnet.add_speaker
data:
  ip_address: "192.168.2.105"
```

## Supported Features

| Feature | Supported |
|---------|-----------|
| Play/Pause/Stop | ✅ |
| Volume Control | ✅ |
| Volume Mute | ✅ |
| Next/Previous Track | ✅ |
| Device Info | ✅ |
| Availability Detection | ✅ |

## Troubleshooting

### Speakers Not Found

1. **Check connectivity**: Ensure Home Assistant can reach the speaker's IP
   ```bash
   ping 192.168.2.100
   curl http://192.168.2.100:1400/xml/device_description.xml
   ```

2. **Check firewall rules**: Port 1400 must be open between subnets

3. **Verify the speaker IP**: Make sure the IP address is correct in the Sonos app

### Speakers Show as Unavailable

1. **Check network routing**: Ensure bidirectional communication is possible
2. **Increase timeout**: Try increasing the scan timeout
3. **Check speaker status**: Ensure the Sonos speaker is powered on and connected

### Volume or Playback Controls Not Working

1. **Check UPnP**: Ensure UPnP is not blocked by your firewall
2. **Check logs**: Enable debug logging to see detailed error messages

```yaml
logger:
  logs:
    custom_components.sonos_subnet: debug
```

## Compatibility

- **Home Assistant**: 2024.1.0 or newer
- **Sonos Speakers**: All Sonos speakers with HTTP API support
- **Network**: Requires TCP connectivity on port 1400

## Known Limitations

- This integration does not support Sonos S1 (legacy) speakers
- Group management is not currently supported
- Media browsing is not implemented (use the official Sonos app)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Sonos, Inc. Sonos is a trademark of Sonos, Inc.
