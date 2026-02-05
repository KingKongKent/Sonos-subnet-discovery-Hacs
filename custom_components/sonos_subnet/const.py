"""Constants for the Sonos Subnet Discovery integration."""
from typing import Final

DOMAIN: Final = "sonos_subnet"

# Configuration keys
CONF_SPEAKER_IPS: Final = "speaker_ips"
CONF_SCAN_SUBNET: Final = "scan_subnet"
CONF_SUBNET_RANGE: Final = "subnet_range"
CONF_SCAN_TIMEOUT: Final = "scan_timeout"

# Defaults
DEFAULT_SCAN_TIMEOUT: Final = 5
DEFAULT_PORT: Final = 1400

# Services
SERVICE_SCAN_SUBNET: Final = "scan_subnet"
SERVICE_ADD_SPEAKER: Final = "add_speaker"
SERVICE_JOIN: Final = "join"
SERVICE_UNJOIN: Final = "unjoin"
SERVICE_SNAPSHOT: Final = "snapshot"
SERVICE_RESTORE: Final = "restore"
SERVICE_SET_SLEEP_TIMER: Final = "set_sleep_timer"
SERVICE_CLEAR_SLEEP_TIMER: Final = "clear_sleep_timer"
SERVICE_PLAY_FAVORITE: Final = "play_favorite"

# Attributes
ATTR_IP_ADDRESS: Final = "ip_address"
ATTR_SPEAKER_INFO: Final = "speaker_info"
ATTR_HOUSEHOLD_ID: Final = "household_id"
ATTR_MODEL_NAME: Final = "model_name"
ATTR_ZONE_NAME: Final = "zone_name"
ATTR_MASTER: Final = "master"
ATTR_WITH_GROUP: Final = "with_group"
ATTR_SLEEP_TIME: Final = "sleep_time"
ATTR_FAVORITE_ID: Final = "favorite_id"

# Scan settings
SONOS_PORT: Final = 1400
SCAN_BATCH_SIZE: Final = 50

# EQ Settings
EQ_BASS: Final = "bass"
EQ_TREBLE: Final = "treble"
EQ_BALANCE: Final = "balance"
EQ_LOUDNESS: Final = "loudness"
EQ_NIGHT_MODE: Final = "night_mode"
EQ_SPEECH_ENHANCEMENT: Final = "speech_enhancement"

# Switches
SWITCH_CROSSFADE: Final = "crossfade"
SWITCH_STATUS_LIGHT: Final = "status_light"
SWITCH_TOUCH_CONTROLS: Final = "touch_controls"
SWITCH_SHUFFLE: Final = "shuffle"
SWITCH_REPEAT: Final = "repeat"

# UPnP Services
UPNP_AV_TRANSPORT: Final = "AVTransport"
UPNP_RENDERING_CONTROL: Final = "RenderingControl"
UPNP_DEVICE_PROPERTIES: Final = "DeviceProperties"
UPNP_GROUP_RENDERING_CONTROL: Final = "GroupRenderingControl"
UPNP_CONTENT_DIRECTORY: Final = "ContentDirectory"
UPNP_ZONE_GROUP_TOPOLOGY: Final = "ZoneGroupTopology"

# UPnP Control URLs
CONTROL_AV_TRANSPORT: Final = "/MediaRenderer/AVTransport/Control"
CONTROL_RENDERING: Final = "/MediaRenderer/RenderingControl/Control"
CONTROL_DEVICE_PROPERTIES: Final = "/DeviceProperties/Control"
CONTROL_GROUP_RENDERING: Final = "/MediaRenderer/GroupRenderingControl/Control"
CONTROL_CONTENT_DIRECTORY: Final = "/MediaServer/ContentDirectory/Control"
CONTROL_ZONE_GROUP: Final = "/ZoneGroupTopology/Control"

# Media types
SONOS_ALBUM_ART_URI: Final = "album_art_uri"
SONOS_TRACK_TITLE: Final = "track_title"
SONOS_TRACK_ARTIST: Final = "track_artist"
SONOS_TRACK_ALBUM: Final = "track_album"
SONOS_TRACK_DURATION: Final = "track_duration"
SONOS_TRACK_POSITION: Final = "track_position"

# Repeat modes
REPEAT_OFF: Final = "off"
REPEAT_ALL: Final = "all"
REPEAT_ONE: Final = "one"
