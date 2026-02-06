"""DataUpdateCoordinator for Sonos Subnet Discovery."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_SPEAKER_IPS,
    SONOS_PORT,
    CONTROL_AV_TRANSPORT,
    CONTROL_RENDERING,
    CONTROL_DEVICE_PROPERTIES,
    UPNP_AV_TRANSPORT,
    UPNP_RENDERING_CONTROL,
    UPNP_DEVICE_PROPERTIES,
)
from .discovery import get_speaker_info
from .helpers import send_upnp_command, extract_xml_value, extract_xml_value_int, extract_xml_value_bool, parse_didl_metadata, parse_duration

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)


class SonosSubnetCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage Sonos speakers on remote subnets."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self._speakers: dict[str, dict[str, Any]] = {}
        self._speaker_ips: list[str] = list(entry.data.get(CONF_SPEAKER_IPS, []))

    @property
    def speakers(self) -> dict[str, dict[str, Any]]:
        """Return all discovered speakers."""
        return self._speakers

    @property
    def speaker_ips(self) -> list[str]:
        """Return configured speaker IPs."""
        return self._speaker_ips

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from all configured Sonos speakers."""
        speakers_data: dict[str, Any] = {}
        
        if not self._speaker_ips:
            _LOGGER.debug("No speaker IPs configured")
            return speakers_data

        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = []
                for ip in self._speaker_ips:
                    tasks.append(self._update_speaker(session, ip))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for ip, result in zip(self._speaker_ips, results):
                    if isinstance(result, Exception):
                        _LOGGER.warning("Error updating speaker %s: %s", ip, result)
                        if ip in self._speakers:
                            speakers_data[ip] = self._speakers[ip]
                            speakers_data[ip]["available"] = False
                    elif result:
                        speakers_data[ip] = result
                        speakers_data[ip]["available"] = True
                    else:
                        _LOGGER.warning("Speaker %s not responding", ip)
                        if ip in self._speakers:
                            speakers_data[ip] = self._speakers[ip]
                            speakers_data[ip]["available"] = False

        except Exception as err:
            raise UpdateFailed(f"Error communicating with Sonos speakers: {err}") from err

        self._speakers = speakers_data
        return speakers_data

    async def _update_speaker(
        self,
        session: aiohttp.ClientSession,
        ip: str,
    ) -> dict[str, Any] | None:
        """Update data for a single speaker."""
        speaker_info = await get_speaker_info(session, ip, timeout=5)
        
        if not speaker_info:
            return None
        
        # Fetch all additional data in parallel
        transport_task = self._get_transport_info(ip)
        position_task = self._get_position_info(ip)
        volume_task = self._get_volume_info(ip)
        eq_task = self._get_eq_info(ip)
        device_settings_task = self._get_device_settings(ip)
        zone_group_task = self._get_zone_group_info(ip)
        
        results = await asyncio.gather(
            transport_task,
            position_task,
            volume_task,
            eq_task,
            device_settings_task,
            zone_group_task,
            return_exceptions=True,
        )
        
        for result in results:
            if isinstance(result, dict):
                speaker_info.update(result)
        
        return speaker_info

    async def _get_transport_info(self, ip: str) -> dict[str, Any]:
        """Get transport info (play state, shuffle, repeat)."""
        data = {}
        
        # Get transport info
        success, response = await send_upnp_command(
            ip,
            UPNP_AV_TRANSPORT,
            "GetTransportInfo",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            data["transport_state"] = extract_xml_value(response, "CurrentTransportState") or "STOPPED"
            data["transport_status"] = extract_xml_value(response, "CurrentTransportStatus")
        
        # Get transport settings (shuffle, repeat)
        success, response = await send_upnp_command(
            ip,
            UPNP_AV_TRANSPORT,
            "GetTransportSettings",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            play_mode = extract_xml_value(response, "PlayMode") or "NORMAL"
            data["shuffle"] = "SHUFFLE" in play_mode
            data["repeat"] = "REPEAT" in play_mode
            data["repeat_one"] = play_mode == "REPEAT_ONE"
        
        # Get crossfade mode
        success, response = await send_upnp_command(
            ip,
            UPNP_AV_TRANSPORT,
            "GetCrossfadeMode",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            data["crossfade"] = extract_xml_value_bool(response, "CrossfadeMode")
        
        return data

    async def _get_position_info(self, ip: str) -> dict[str, Any]:
        """Get current track position info."""
        data = {}
        
        success, response = await send_upnp_command(
            ip,
            UPNP_AV_TRANSPORT,
            "GetPositionInfo",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            data["track_number"] = extract_xml_value_int(response, "Track")
            data["track_duration"] = parse_duration(extract_xml_value(response, "TrackDuration") or "")
            data["track_position"] = parse_duration(extract_xml_value(response, "RelTime") or "")
            track_uri = extract_xml_value(response, "TrackURI") or ""
            data["track_uri"] = track_uri
            
            # Parse track metadata
            metadata_raw = extract_xml_value(response, "TrackMetaData")
            if metadata_raw:
                metadata = parse_didl_metadata(metadata_raw)
                data["track_title"] = metadata.get("title")
                data["track_artist"] = metadata.get("artist")
                data["track_album"] = metadata.get("album")
                data["album_art_uri"] = metadata.get("album_art")
                
                # Fallback: If no title and it's a stream, try to get stream info
                if not data.get("track_title") and ("http" in track_uri or "x-rincon-mp3radio" in track_uri or "x-sonosapi-stream" in track_uri):
                    # For streaming services, try additional fields
                    stream_info = extract_xml_value(response, "StreamContent") or metadata.get("stream_content")
                    if stream_info:
                        data["track_title"] = stream_info
                    
                    # Try to get radio show name
                    radio_show = metadata.get("radio_show") or extract_xml_value(metadata_raw, "r:streamContent")
                    if radio_show and not data.get("track_artist"):
                        data["track_artist"] = radio_show
        
        return data

    async def _get_volume_info(self, ip: str) -> dict[str, Any]:
        """Get volume and mute status."""
        data = {}
        
        # Get volume
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetVolume",
            "<InstanceID>0</InstanceID><Channel>Master</Channel>",
            CONTROL_RENDERING,
        )
        
        if success:
            data["volume"] = extract_xml_value_int(response, "CurrentVolume")
        
        # Get mute
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetMute",
            "<InstanceID>0</InstanceID><Channel>Master</Channel>",
            CONTROL_RENDERING,
        )
        
        if success:
            data["mute"] = extract_xml_value_bool(response, "CurrentMute")
        
        return data

    async def _get_eq_info(self, ip: str) -> dict[str, Any]:
        """Get EQ settings (bass, treble, loudness, etc.)."""
        data = {}
        
        # Get bass
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetBass",
            "<InstanceID>0</InstanceID>",
            CONTROL_RENDERING,
        )
        if success:
            data["bass"] = extract_xml_value_int(response, "CurrentBass")
        
        # Get treble
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetTreble",
            "<InstanceID>0</InstanceID>",
            CONTROL_RENDERING,
        )
        if success:
            data["treble"] = extract_xml_value_int(response, "CurrentTreble")
        
        # Get loudness
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetLoudness",
            "<InstanceID>0</InstanceID><Channel>Master</Channel>",
            CONTROL_RENDERING,
        )
        if success:
            data["loudness"] = extract_xml_value_bool(response, "CurrentLoudness")
        
        # Get night mode (soundbars only - may fail on other devices)
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetEQ",
            "<InstanceID>0</InstanceID><EQType>NightMode</EQType>",
            CONTROL_RENDERING,
        )
        if success:
            data["night_mode"] = extract_xml_value_bool(response, "CurrentValue")
        
        # Get speech enhancement (soundbars only)
        success, response = await send_upnp_command(
            ip,
            UPNP_RENDERING_CONTROL,
            "GetEQ",
            "<InstanceID>0</InstanceID><EQType>DialogLevel</EQType>",
            CONTROL_RENDERING,
        )
        if success:
            data["speech_enhancement"] = extract_xml_value_bool(response, "CurrentValue")
        
        return data

    async def _get_device_settings(self, ip: str) -> dict[str, Any]:
        """Get device settings (LED, touch controls, etc.)."""
        data = {}
        
        # Get LED state
        success, response = await send_upnp_command(
            ip,
            UPNP_DEVICE_PROPERTIES,
            "GetLEDState",
            "",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            led_state = extract_xml_value(response, "CurrentLEDState")
            data["status_light"] = led_state == "On" if led_state else True
        
        # Get button lock state (touch controls)
        success, response = await send_upnp_command(
            ip,
            UPNP_DEVICE_PROPERTIES,
            "GetButtonLockState",
            "",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            lock_state = extract_xml_value(response, "CurrentButtonLockState")
            data["touch_controls"] = lock_state != "On" if lock_state else True
        
        return data

    async def async_add_speaker(self, ip: str, speaker_info: dict[str, Any]) -> None:
        """Add a new speaker to the coordinator."""
        if ip not in self._speaker_ips:
            self._speaker_ips.append(ip)
            self._speakers[ip] = speaker_info
            
            new_data = dict(self.entry.data)
            new_data[CONF_SPEAKER_IPS] = self._speaker_ips
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            
            await self.async_request_refresh()

    async def async_remove_speaker(self, ip: str) -> None:
        """Remove a speaker from the coordinator."""
        if ip in self._speaker_ips:
            self._speaker_ips.remove(ip)
            self._speakers.pop(ip, None)
            
            new_data = dict(self.entry.data)
            new_data[CONF_SPEAKER_IPS] = self._speaker_ips
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def _get_zone_group_info(self, ip: str) -> dict[str, Any]:
        """Get zone group topology to detect grouping."""
        data = {"group_members": [], "is_coordinator": True}
        
        success, response = await send_upnp_command(
            ip,
            "urn:schemas-upnp-org:service:ZoneGroupTopology:1",
            "GetZoneGroupState",
            "",
            "/ZoneGroupTopology/Control",
        )
        
        if not success:
            _LOGGER.debug("Failed to get zone group state for %s", ip)
            return data
        
        try:
            import re
            
            # Get this speaker's UUID
            speaker_uuid = None
            for speaker_ip, speaker_info in self._speakers.items():
                if speaker_ip == ip:
                    speaker_uuid = speaker_info.get("uuid")
                    break
            
            if not speaker_uuid:
                _LOGGER.debug("No UUID found for speaker %s", ip)
                return data
            
            # Extract ZoneGroupState
            state_match = re.search(r'<ZoneGroupState>(.*?)</ZoneGroupState>', response, re.DOTALL)
            if not state_match:
                _LOGGER.debug("No ZoneGroupState found in response for %s", ip)
                return data
            
            zone_state = state_match.group(1)
            # Unescape XML entities
            zone_state = zone_state.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
            
            _LOGGER.debug("Zone state for %s: %s", ip, zone_state[:500])
            
            # Find all ZoneGroups
            zone_groups = re.findall(r'<ZoneGroup([^>]*)>(.*?)</ZoneGroup>', zone_state, re.DOTALL)
            
            for group_attrs, group_content in zone_groups:
                # Get coordinator UUID from ZoneGroup attributes
                coordinator_match = re.search(r'Coordinator="([^"]+)"', group_attrs)
                if not coordinator_match:
                    continue
                
                coordinator_uuid = coordinator_match.group(1)
                
                # Get all members in this group
                member_pattern = r'<ZoneGroupMember[^>]*UUID="([^"]+)"[^>]*Location="http://([^:]+):'
                members = re.findall(member_pattern, group_content)
                
                _LOGGER.debug("Found group with coordinator %s, members: %s", coordinator_uuid, members)
                
                # Check if this speaker is in this group
                speaker_in_group = False
                for member_uuid, member_ip in members:
                    if member_uuid == speaker_uuid or member_ip == ip:
                        speaker_in_group = True
                        break
                
                if speaker_in_group:
                    # This is our speaker's group
                    group_member_ips = [m_ip for _, m_ip in members]
                    data["group_members"] = group_member_ips
                    data["is_coordinator"] = (coordinator_uuid == speaker_uuid)
                    
                    _LOGGER.debug("Speaker %s is in group: %s, is_coordinator: %s", 
                                ip, group_member_ips, data["is_coordinator"])
                    break
            
        except Exception as err:
            _LOGGER.error("Error parsing zone group state for %s: %s", ip, err)
        
        return data

    def get_ip_from_entity_id(self, entity_id: str) -> str | None:
        """Convert entity_id to IP address."""
        for ip, info in self._speakers.items():
            zone_name = info.get("zone_name", "")
            # Create entity_id from zone_name
            expected_id = f"media_player.{zone_name.lower().replace(' ', '_')}"
            if expected_id == entity_id:
                return ip
        return None
