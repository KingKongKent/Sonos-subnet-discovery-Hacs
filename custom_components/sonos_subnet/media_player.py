"""Media player platform for Sonos Subnet Discovery."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import soco

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

SUPPORTED_FEATURES = (
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
    | MediaPlayerEntityFeature.GROUPING
)


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
        # Base ID for device grouping (shared across all entity types)
        self._device_id = speaker_info.get("uuid") or speaker_info.get("serial_number") or ip_address
        # Prefix unique_id to avoid collision with built-in Sonos integration
        self._attr_unique_id = f"sonos_subnet_{self._device_id}"
        
        # Create SoCo instance for direct speaker control
        self._soco = soco.SoCo(ip_address)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return SUPPORTED_FEATURES

    @property
    def ip_address(self) -> str:
        """Return the IP address of this speaker."""
        return self._ip_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this speaker."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
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
        title = self._speaker_data.get("track_title")
        
        # Fallback: If no title, try to parse from URI for streaming radio
        if not title:
            track_uri = self._speaker_data.get("track_uri", "")
            if track_uri:
                # Don't show raw URIs, return None instead so HA can handle it
                if track_uri.startswith(("http://", "https://", "x-rincon", "x-sonos")):
                    return None
        
        return title

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

    @property
    def group_members(self) -> list[str] | None:
        """Return list of entity_ids of group members."""
        member_ips = self._speaker_data.get("group_members", [])
        
        _LOGGER.debug("Speaker %s group_members from data: %s", self._ip_address, member_ips)
        
        if not member_ips or len(member_ips) <= 1:
            return None
        
        # Convert IPs to entity_ids
        entity_ids = []
        for ip in member_ips:
            if ip in self.coordinator.speakers:
                info = self.coordinator.speakers[ip]
                zone_name = info.get("zone_name", "")
                if zone_name:
                    entity_id = f"media_player.{zone_name.lower().replace(' ', '_')}"
                    entity_ids.append(entity_id)
                    _LOGGER.debug("Mapped IP %s to entity %s", ip, entity_id)
        
        _LOGGER.debug("Final group_members for %s: %s", self._ip_address, entity_ids)
        return entity_ids if entity_ids else None

    # Transport Controls (via SoCo)
    async def async_media_play(self) -> None:
        """Send play command."""
        _LOGGER.info("Sending PLAY command to %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.play)
        except Exception as exc:
            _LOGGER.error("SoCo play failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        _LOGGER.info("Sending PAUSE command to %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.pause)
        except Exception as exc:
            _LOGGER.error("SoCo pause failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        _LOGGER.info("Sending STOP command to %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.stop)
        except Exception as exc:
            _LOGGER.error("SoCo stop failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        _LOGGER.info("Sending NEXT command to %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.next)
        except Exception as exc:
            _LOGGER.error("SoCo next failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        _LOGGER.info("Sending PREVIOUS command to %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.previous)
        except Exception as exc:
            _LOGGER.error("SoCo previous failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_media_seek(self, position: float) -> None:
        """Seek to a position."""
        hours = int(position // 3600)
        minutes = int((position % 3600) // 60)
        seconds = int(position % 60)
        target = f"{hours}:{minutes:02d}:{seconds:02d}"
        
        _LOGGER.info("Seeking to %s on %s", target, self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.seek, target)
        except Exception as exc:
            _LOGGER.error("SoCo seek failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    async def async_clear_playlist(self) -> None:
        """Clear the queue."""
        _LOGGER.info("Clearing queue on %s", self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._soco.clear_queue)
        except Exception as exc:
            _LOGGER.error("SoCo clear queue failed for %s: %s", self._ip_address, exc)
            return
        await self.coordinator.async_request_refresh()

    # Volume Controls (via SoCo)
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        volume_percent = int(volume * 100)
        _LOGGER.warning(
            "Setting volume to %d%% on %s (entity=%s, features=%s)",
            volume_percent,
            self._ip_address,
            self.entity_id,
            self.supported_features,
        )
        try:
            await self.hass.async_add_executor_job(
                self._set_soco_volume, volume_percent
            )
        except Exception as exc:
            _LOGGER.error("SoCo set volume failed for %s: %s", self._ip_address, exc)
            return
        # Optimistically update local state so the UI slider doesn't snap back
        if self.coordinator.data and self._ip_address in self.coordinator.data:
            self.coordinator.data[self._ip_address]["volume"] = volume_percent
        self.async_write_ha_state()

    def _set_soco_volume(self, volume: int) -> None:
        """Set volume via SoCo (runs in executor)."""
        self._soco.volume = volume

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        current = self.volume_level or 0
        await self.async_set_volume_level(min(1.0, current + 0.05))

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        current = self.volume_level or 0
        await self.async_set_volume_level(max(0.0, current - 0.05))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        _LOGGER.info("Setting mute to %s on %s", mute, self._ip_address)
        try:
            await self.hass.async_add_executor_job(self._set_soco_mute, mute)
        except Exception as exc:
            _LOGGER.error("SoCo set mute failed for %s: %s", self._ip_address, exc)
            return
        # Optimistically update local state
        if self.coordinator.data and self._ip_address in self.coordinator.data:
            self.coordinator.data[self._ip_address]["mute"] = mute
        self.async_write_ha_state()

    def _set_soco_mute(self, mute: bool) -> None:
        """Set mute via SoCo (runs in executor)."""
        self._soco.mute = mute

    # Shuffle/Repeat (via SoCo)
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
        try:
            await self.hass.async_add_executor_job(
                self._set_soco_play_mode, play_mode
            )
        except Exception:
            # Fallback to UPnP
            await self._send_av_transport_command(
                "SetPlayMode",
                f"<InstanceID>0</InstanceID><NewPlayMode>{play_mode}</NewPlayMode>"
            )
        await self.coordinator.async_request_refresh()

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
        try:
            await self.hass.async_add_executor_job(
                self._set_soco_play_mode, play_mode
            )
        except Exception:
            # Fallback to UPnP
            await self._send_av_transport_command(
                "SetPlayMode",
                f"<InstanceID>0</InstanceID><NewPlayMode>{play_mode}</NewPlayMode>"
            )
        await self.coordinator.async_request_refresh()

    def _set_soco_play_mode(self, mode: str) -> None:
        """Set play mode via SoCo (runs in executor)."""
        self._soco.play_mode = mode

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

    # Grouping Methods
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join other players to this player (this player becomes coordinator)."""
        _LOGGER.warning("async_join_players CALLED! Master: %s, Members to join: %s", self.entity_id, group_members)
        _LOGGER.warning("Master UUID: %s, Master IP: %s", self._speaker_info.get("uuid"), self._ip_address)
        
        # Get this speaker's UUID (master/coordinator)
        master_uuid = self._speaker_info.get("uuid", "")
        if not master_uuid:
            _LOGGER.error("Cannot group: master speaker UUID not found for %s", self.entity_id)
            return
        
        coordinator_uri = f"x-rincon:{master_uuid}"
        _LOGGER.warning("Coordinator URI: %s", coordinator_uri)
        
        # Join each member to this coordinator
        for member_entity_id in group_members:
            # Skip if trying to join to itself
            if member_entity_id == self.entity_id:
                _LOGGER.debug("Skipping self: %s", member_entity_id)
                continue
            
            # Convert entity_id to IP
            member_ip = self.coordinator.get_ip_from_entity_id(member_entity_id)
            if not member_ip:
                _LOGGER.error("Could not find IP for entity %s", member_entity_id)
                continue
            
            _LOGGER.warning("Joining %s (%s) to coordinator %s (%s)", member_entity_id, member_ip, self.entity_id, self._ip_address)
            
            success, _ = await send_upnp_command(
                member_ip,
                UPNP_AV_TRANSPORT,
                "SetAVTransportURI",
                f"<InstanceID>0</InstanceID><CurrentURI>{coordinator_uri}</CurrentURI><CurrentURIMetaData></CurrentURIMetaData>",
                CONTROL_AV_TRANSPORT,
            )
            
            if not success:
                _LOGGER.error("Failed to join %s to group", member_entity_id)
        
        # Request refresh after grouping
        await self.coordinator.async_request_refresh()

    async def async_unjoin_player(self) -> None:
        """Unjoin this player from its group."""
        _LOGGER.warning("async_unjoin_player CALLED! Entity: %s, IP: %s", self.entity_id, self._ip_address)
        
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_AV_TRANSPORT,
            "BecomeCoordinatorOfStandaloneGroup",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to unjoin %s from group", self.entity_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._ip_address in self.coordinator.data:
            self._speaker_info.update(self.coordinator.data[self._ip_address])
        self.async_write_ha_state()
