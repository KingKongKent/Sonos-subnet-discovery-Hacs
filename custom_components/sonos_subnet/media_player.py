"""Media player platform for Sonos Subnet Discovery."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    MediaPlayerEnqueue,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SONOS_PORT,
    CONTROL_AV_TRANSPORT,
    CONTROL_RENDERING,
    UPNP_AV_TRANSPORT,
    UPNP_RENDERING_CONTROL,
)
from .coordinator import SonosSubnetCoordinator
from .helpers import send_upnp_command, escape_xml

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos media player from a config entry."""
    coordinator: SonosSubnetCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SonosSubnetMediaPlayer] = []

    for ip, speaker_info in coordinator.speakers.items():
        entities.append(SonosSubnetMediaPlayer(coordinator, ip, speaker_info))

    async_add_entities(entities)

    @callback
    def async_add_new_speakers() -> None:
        """Add any new speakers that appear in the coordinator."""
        existing_ips = {entity.ip_address for entity in entities}
        new_entities = []

        for ip, speaker_info in coordinator.speakers.items():
            if ip not in existing_ips:
                new_entity = SonosSubnetMediaPlayer(coordinator, ip, speaker_info)
                entities.append(new_entity)
                new_entities.append(new_entity)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        coordinator.async_add_listener(async_add_new_speakers)
    )


class SonosSubnetMediaPlayer(CoordinatorEntity[SonosSubnetCoordinator], MediaPlayerEntity):
    """Representation of a Sonos speaker on a remote subnet."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        
        self._ip_address = ip_address
        self._speaker_info = speaker_info
        self._attr_unique_id = speaker_info.get("uuid") or speaker_info.get("serial_number") or ip_address
        
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.SEEK
            | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        )

    @property
    def ip_address(self) -> str:
        """Return the IP address of this speaker."""
        return self._ip_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this speaker."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._speaker_info.get("zone_name", f"Sonos ({self._ip_address})"),
            manufacturer="Sonos",
            model=self._speaker_info.get("model_name", "Unknown"),
            sw_version=self._speaker_info.get("software_version"),
            hw_version=self._speaker_info.get("hardware_version"),
            configuration_url=f"http://{self._ip_address}:{SONOS_PORT}/",
        )

    @property
    def _speaker_data(self) -> dict[str, Any]:
        """Return current speaker data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._ip_address, {})
        return {}

    @property
    def available(self) -> bool:
        """Return if the speaker is available."""
        return self._speaker_data.get("available", False)

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        if not self.available:
            return MediaPlayerState.OFF
        
        transport_state = self._speaker_data.get("transport_state", "").upper()
        
        state_map = {
            "PLAYING": MediaPlayerState.PLAYING,
            "PAUSED_PLAYBACK": MediaPlayerState.PAUSED,
            "PAUSED": MediaPlayerState.PAUSED,
            "STOPPED": MediaPlayerState.IDLE,
            "TRANSITIONING": MediaPlayerState.BUFFERING,
        }
        
        return state_map.get(transport_state, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0..1)."""
        volume = self._speaker_data.get("volume")
        if volume is not None:
            return volume / 100
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return if volume is muted."""
        return self._speaker_data.get("mute")

    @property
    def shuffle(self) -> bool | None:
        """Return if shuffle is enabled."""
        return self._speaker_data.get("shuffle")

    @property
    def repeat(self) -> RepeatMode | None:
        """Return repeat mode."""
        if self._speaker_data.get("repeat_one"):
            return RepeatMode.ONE
        elif self._speaker_data.get("repeat"):
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        return self._speaker_data.get("track_title")

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        return self._speaker_data.get("track_artist")

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        return self._speaker_data.get("track_album")

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        album_art = self._speaker_data.get("album_art_uri")
        if album_art:
            if album_art.startswith("http"):
                return album_art
            return f"http://{self._ip_address}:{SONOS_PORT}{album_art}"
        return None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        return self._speaker_data.get("track_duration")

    @property
    def media_position(self) -> int | None:
        """Return the position of current playing media in seconds."""
        return self._speaker_data.get("track_position")

    @property
    def media_track(self) -> int | None:
        """Return the track number of current playing media."""
        return self._speaker_data.get("track_number")

    # Transport Controls
    async def async_media_play(self) -> None:
        """Send play command."""
        _LOGGER.info("Sending PLAY command to %s", self._ip_address)
        await self._send_av_transport_command("Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        _LOGGER.info("Sending PAUSE command to %s", self._ip_address)
        await self._send_av_transport_command("Pause", "<InstanceID>0</InstanceID>")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        _LOGGER.info("Sending STOP command to %s", self._ip_address)
        await self._send_av_transport_command("Stop", "<InstanceID>0</InstanceID>")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        _LOGGER.info("Sending NEXT command to %s", self._ip_address)
        await self._send_av_transport_command("Next", "<InstanceID>0</InstanceID>")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        _LOGGER.info("Sending PREVIOUS command to %s", self._ip_address)
        await self._send_av_transport_command("Previous", "<InstanceID>0</InstanceID>")

    async def async_media_seek(self, position: float) -> None:
        """Seek to a position."""
        hours = int(position // 3600)
        minutes = int((position % 3600) // 60)
        seconds = int(position % 60)
        target = f"{hours}:{minutes:02d}:{seconds:02d}"
        
        _LOGGER.info("Seeking to %s on %s", target, self._ip_address)
        await self._send_av_transport_command(
            "Seek",
            f"<InstanceID>0</InstanceID><Unit>REL_TIME</Unit><Target>{target}</Target>"
        )

    async def async_clear_playlist(self) -> None:
        """Clear the queue."""
        _LOGGER.info("Clearing queue on %s", self._ip_address)
        await self._send_av_transport_command(
            "RemoveAllTracksFromQueue",
            "<InstanceID>0</InstanceID>"
        )

    # Volume Controls
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        volume_percent = int(volume * 100)
        _LOGGER.info("Setting volume to %d%% on %s", volume_percent, self._ip_address)
        await self._send_rendering_command(
            "SetVolume",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>{volume_percent}</DesiredVolume>"
        )

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        current = self.volume_level or 0
        await self.async_set_volume_level(min(1.0, current + 0.02))

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        current = self.volume_level or 0
        await self.async_set_volume_level(max(0.0, current - 0.02))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        mute_value = "1" if mute else "0"
        _LOGGER.info("Setting mute to %s on %s", mute, self._ip_address)
        await self._send_rendering_command(
            "SetMute",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredMute>{mute_value}</DesiredMute>"
        )

    # Shuffle/Repeat
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        current_repeat = self._speaker_data.get("repeat", False)
        current_repeat_one = self._speaker_data.get("repeat_one", False)
        
        if current_repeat_one:
            play_mode = "SHUFFLE_REPEAT_ONE" if shuffle else "REPEAT_ONE"
        elif current_repeat:
            play_mode = "SHUFFLE_REPEAT_ALL" if shuffle else "REPEAT_ALL"
        else:
            play_mode = "SHUFFLE_NOREPEAT" if shuffle else "NORMAL"
        
        _LOGGER.info("Setting play mode to %s on %s", play_mode, self._ip_address)
        await self._send_av_transport_command(
            "SetPlayMode",
            f"<InstanceID>0</InstanceID><NewPlayMode>{play_mode}</NewPlayMode>"
        )

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        current_shuffle = self._speaker_data.get("shuffle", False)
        
        if repeat == RepeatMode.ONE:
            play_mode = "SHUFFLE_REPEAT_ONE" if current_shuffle else "REPEAT_ONE"
        elif repeat == RepeatMode.ALL:
            play_mode = "SHUFFLE_REPEAT_ALL" if current_shuffle else "REPEAT_ALL"
        else:
            play_mode = "SHUFFLE_NOREPEAT" if current_shuffle else "NORMAL"
        
        _LOGGER.info("Setting play mode to %s on %s", play_mode, self._ip_address)
        await self._send_av_transport_command(
            "SetPlayMode",
            f"<InstanceID>0</InstanceID><NewPlayMode>{play_mode}</NewPlayMode>"
        )

    # Play Media
    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play media from a URL or media ID."""
        _LOGGER.info("Playing media %s on %s", media_id, self._ip_address)
        
        # Create DIDL-Lite metadata
        didl = f'''<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/">
<item id="1" parentID="0" restricted="1">
<dc:title>Audio Stream</dc:title>
<upnp:class>object.item.audioItem.musicTrack</upnp:class>
<res protocolInfo="http-get:*:audio/mpeg:*">{escape_xml(media_id)}</res>
</item>
</DIDL-Lite>'''
        
        escaped_uri = escape_xml(media_id)
        escaped_didl = escape_xml(didl)
        
        # Set the URI
        await self._send_av_transport_command(
            "SetAVTransportURI",
            f"<InstanceID>0</InstanceID><CurrentURI>{escaped_uri}</CurrentURI><CurrentURIMetaData>{escaped_didl}</CurrentURIMetaData>"
        )
        
        # Start playback
        await self.async_media_play()

    # UPnP Command Helpers
    async def _send_av_transport_command(self, action: str, arguments: str) -> bool:
        """Send an AVTransport command to the speaker."""
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_AV_TRANSPORT,
            action,
            arguments,
            CONTROL_AV_TRANSPORT,
        )
        if success:
            await self.coordinator.async_request_refresh()
        return success

    async def _send_rendering_command(self, action: str, arguments: str) -> bool:
        """Send a rendering control command to the speaker."""
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            action,
            arguments,
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()
        return success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._ip_address in self.coordinator.data:
            self._speaker_info.update(self.coordinator.data[self._ip_address])
        self.async_write_ha_state()
