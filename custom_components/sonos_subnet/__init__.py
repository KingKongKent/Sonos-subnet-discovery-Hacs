"""The Sonos Subnet Discovery integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_SPEAKER_IPS,
    SERVICE_SCAN_SUBNET,
    SERVICE_ADD_SPEAKER,
    SERVICE_JOIN,
    SERVICE_UNJOIN,
    SERVICE_SET_SLEEP_TIMER,
    SERVICE_CLEAR_SLEEP_TIMER,
    ATTR_IP_ADDRESS,
    ATTR_MASTER,
    ATTR_SLEEP_TIME,
    CONTROL_AV_TRANSPORT,
    UPNP_AV_TRANSPORT,
)
from .coordinator import SonosSubnetCoordinator
from .discovery import scan_subnet_for_sonos, validate_sonos_ip
from .helpers import send_upnp_command

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SWITCH,
]

SERVICE_SCAN_SCHEMA = vol.Schema({
    vol.Required("subnet"): str,
    vol.Optional("timeout", default=5): vol.Coerce(int),
})

SERVICE_ADD_SPEAKER_SCHEMA = vol.Schema({
    vol.Required(ATTR_IP_ADDRESS): str,
})

SERVICE_JOIN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_IP_ADDRESS): str,
    vol.Optional(ATTR_MASTER): str,
    vol.Optional("entity_id"): str,
    vol.Optional("master_entity_id"): str,
})

SERVICE_UNJOIN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_IP_ADDRESS): str,
    vol.Optional("entity_id"): str,
})

SERVICE_SLEEP_TIMER_SCHEMA = vol.Schema({
    vol.Required(ATTR_IP_ADDRESS): str,
    vol.Required(ATTR_SLEEP_TIME): vol.All(vol.Coerce(int), vol.Range(min=1, max=7200)),
})

SERVICE_CLEAR_SLEEP_TIMER_SCHEMA = vol.Schema({
    vol.Required(ATTR_IP_ADDRESS): str,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos Subnet Discovery from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SonosSubnetCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_scan_subnet(call: ServiceCall) -> dict[str, Any]:
        """Handle the scan_subnet service call."""
        subnet = call.data["subnet"]
        timeout = call.data.get("timeout", 5)
        
        _LOGGER.info("Scanning subnet %s for Sonos devices", subnet)
        devices = await scan_subnet_for_sonos(hass, subnet, timeout)
        
        _LOGGER.info("Found %d Sonos devices on subnet %s", len(devices), subnet)
        
        # Fire an event with the discovered devices
        hass.bus.async_fire(f"{DOMAIN}_devices_discovered", {
            "subnet": subnet,
            "devices": devices,
        })
        
        return {"devices": devices}

    async def handle_add_speaker(call: ServiceCall) -> None:
        """Handle the add_speaker service call."""
        ip_address = call.data[ATTR_IP_ADDRESS]
        
        _LOGGER.info("Adding Sonos speaker at %s", ip_address)
        
        speaker_info = await validate_sonos_ip(hass, ip_address)
        if speaker_info:
            # Add to coordinator
            await coordinator.async_add_speaker(ip_address, speaker_info)
            _LOGGER.info("Successfully added Sonos speaker: %s", speaker_info.get("zone_name", ip_address))
        else:
            _LOGGER.error("No Sonos device found at %s", ip_address)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_SUBNET,
        handle_scan_subnet,
        schema=SERVICE_SCAN_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SPEAKER,
        handle_add_speaker,
        schema=SERVICE_ADD_SPEAKER_SCHEMA,
    )

    # Join/Unjoin services for grouping
    async def handle_join(call: ServiceCall) -> None:
        """Handle the join service call - group a speaker with a master."""
        ip_address = call.data.get(ATTR_IP_ADDRESS)
        master = call.data.get(ATTR_MASTER)
        entity_id = call.data.get("entity_id")
        master_entity_id = call.data.get("master_entity_id")
        
        # Support both entity_id and IP address
        if entity_id:
            ip_address = coordinator.get_ip_from_entity_id(entity_id)
            if not ip_address:
                _LOGGER.error("Entity %s not found", entity_id)
                return
        
        if master_entity_id:
            master = coordinator.get_ip_from_entity_id(master_entity_id)
            if not master:
                _LOGGER.error("Master entity %s not found", master_entity_id)
                return
        
        if not ip_address or not master:
            _LOGGER.error("Both speaker and master must be specified")
            return
        
        _LOGGER.info("Joining %s to master %s", ip_address, master)
        
        # Get master's coordinator URI
        master_data = coordinator.speakers.get(master, {})
        master_uuid = master_data.get("uuid", "")
        
        if not master_uuid:
            _LOGGER.error("Master speaker %s not found", master)
            return
        
        coordinator_uri = f"x-rincon:{master_uuid}"
        
        success, _ = await send_upnp_command(
            ip_address,
            UPNP_AV_TRANSPORT,
            "SetAVTransportURI",
            f"<InstanceID>0</InstanceID><CurrentURI>{coordinator_uri}</CurrentURI><CurrentURIMetaData></CurrentURIMetaData>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            await coordinator.async_request_refresh()

    async def handle_unjoin(call: ServiceCall) -> None:
        """Handle the unjoin service call - remove speaker from group."""
        ip_address = call.data.get(ATTR_IP_ADDRESS)
        entity_id = call.data.get("entity_id")
        
        # Support both entity_id and IP address
        if entity_id:
            ip_address = coordinator.get_ip_from_entity_id(entity_id)
            if not ip_address:
                _LOGGER.error("Entity %s not found", entity_id)
                return
        
        if not ip_address:
            _LOGGER.error("Speaker must be specified")
            return
        
        _LOGGER.info("Unjoining %s from group", ip_address)
        
        success, _ = await send_upnp_command(
            ip_address,
            UPNP_AV_TRANSPORT,
            "BecomeCoordinatorOfStandaloneGroup",
            "<InstanceID>0</InstanceID>",
            CONTROL_AV_TRANSPORT,
        )
        
        if success:
            await coordinator.async_request_refresh()

    async def handle_set_sleep_timer(call: ServiceCall) -> None:
        """Handle the set_sleep_timer service call."""
        ip_address = call.data[ATTR_IP_ADDRESS]
        sleep_time = call.data[ATTR_SLEEP_TIME]
        
        # Convert seconds to ISO 8601 duration format
        hours = sleep_time // 3600
        minutes = (sleep_time % 3600) // 60
        seconds = sleep_time % 60
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        _LOGGER.info("Setting sleep timer to %s on %s", duration, ip_address)
        
        success, _ = await send_upnp_command(
            ip_address,
            UPNP_AV_TRANSPORT,
            "ConfigureSleepTimer",
            f"<InstanceID>0</InstanceID><NewSleepTimerDuration>{duration}</NewSleepTimerDuration>",
            CONTROL_AV_TRANSPORT,
        )

    async def handle_clear_sleep_timer(call: ServiceCall) -> None:
        """Handle the clear_sleep_timer service call."""
        ip_address = call.data[ATTR_IP_ADDRESS]
        
        _LOGGER.info("Clearing sleep timer on %s", ip_address)
        
        success, _ = await send_upnp_command(
            ip_address,
            UPNP_AV_TRANSPORT,
            "ConfigureSleepTimer",
            "<InstanceID>0</InstanceID><NewSleepTimerDuration></NewSleepTimerDuration>",
            CONTROL_AV_TRANSPORT,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_JOIN,
        handle_join,
        schema=SERVICE_JOIN_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNJOIN,
        handle_unjoin,
        schema=SERVICE_UNJOIN_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SLEEP_TIMER,
        handle_set_sleep_timer,
        schema=SERVICE_SLEEP_TIMER_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_SLEEP_TIMER,
        handle_clear_sleep_timer,
        schema=SERVICE_CLEAR_SLEEP_TIMER_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
