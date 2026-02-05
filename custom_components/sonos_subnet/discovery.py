"""Discovery utilities for finding Sonos devices on remote subnets."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any
from ipaddress import IPv4Network, IPv4Address

import aiohttp

from homeassistant.core import HomeAssistant

from .const import SONOS_PORT, SCAN_BATCH_SIZE, DEFAULT_SCAN_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Sonos device description URL
DEVICE_DESCRIPTION_PATH = "/xml/device_description.xml"


async def check_sonos_device(
    session: aiohttp.ClientSession,
    ip: str,
    timeout: int = DEFAULT_SCAN_TIMEOUT,
) -> dict[str, Any] | None:
    """Check if a Sonos device exists at the given IP address."""
    url = f"http://{ip}:{SONOS_PORT}{DEVICE_DESCRIPTION_PATH}"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status == 200:
                text = await response.text()
                if "Sonos" in text or "sonos" in text.lower():
                    return await get_speaker_info(session, ip, timeout)
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        pass
    
    return None


async def get_speaker_info(
    session: aiohttp.ClientSession,
    ip: str,
    timeout: int = DEFAULT_SCAN_TIMEOUT,
) -> dict[str, Any] | None:
    """Get detailed information about a Sonos speaker."""
    try:
        # Try to get device info from Sonos HTTP API
        status_url = f"http://{ip}:{SONOS_PORT}/status/zp"
        info_url = f"http://{ip}:{SONOS_PORT}/xml/device_description.xml"
        
        speaker_info = {
            "ip_address": ip,
            "port": SONOS_PORT,
        }
        
        # Get zone player status
        try:
            async with session.get(status_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    text = await response.text()
                    # Parse basic info from status
                    speaker_info["status_available"] = True
        except (aiohttp.ClientError, asyncio.TimeoutError):
            speaker_info["status_available"] = False
        
        # Get device description
        async with session.get(info_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status == 200:
                text = await response.text()
                
                # Parse XML for device info (simple parsing)
                speaker_info["zone_name"] = _extract_xml_value(text, "roomName") or _extract_xml_value(text, "friendlyName") or f"Sonos ({ip})"
                speaker_info["model_name"] = _extract_xml_value(text, "modelName") or "Unknown"
                speaker_info["model_number"] = _extract_xml_value(text, "modelNumber") or "Unknown"
                speaker_info["serial_number"] = _extract_xml_value(text, "serialNum") or _extract_xml_value(text, "serialNumber")
                speaker_info["software_version"] = _extract_xml_value(text, "softwareVersion") or _extract_xml_value(text, "swGen")
                speaker_info["hardware_version"] = _extract_xml_value(text, "hardwareVersion")
                speaker_info["mac_address"] = _extract_xml_value(text, "MACAddress")
                speaker_info["household_id"] = _extract_xml_value(text, "householdId")
                
                # Extract UDN for unique identification
                udn = _extract_xml_value(text, "UDN")
                if udn:
                    speaker_info["udn"] = udn
                    # Clean up UUID format
                    if udn.startswith("uuid:"):
                        speaker_info["uuid"] = udn[5:]
                    else:
                        speaker_info["uuid"] = udn
                
                return speaker_info
        
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        _LOGGER.debug("Error getting speaker info from %s: %s", ip, err)
    
    return None


def _extract_xml_value(xml_text: str, tag: str) -> str | None:
    """Extract a value from XML text (simple extraction without full parsing)."""
    import re
    
    # Try different patterns for the tag
    patterns = [
        rf"<{tag}>([^<]+)</{tag}>",
        rf"<{tag}[^>]*>([^<]+)</{tag}>",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, xml_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


async def scan_subnet_for_sonos(
    hass: HomeAssistant,
    subnet: str,
    timeout: int = DEFAULT_SCAN_TIMEOUT,
) -> list[dict[str, Any]]:
    """Scan a subnet for Sonos devices."""
    discovered_devices: list[dict[str, Any]] = []
    
    try:
        network = IPv4Network(subnet, strict=False)
    except ValueError as err:
        _LOGGER.error("Invalid subnet format %s: %s", subnet, err)
        return []
    
    # Get all host IPs in the network
    all_ips = [str(ip) for ip in network.hosts()]
    
    _LOGGER.info("Scanning %d IP addresses in subnet %s", len(all_ips), subnet)
    
    # Use connection pooling for efficiency
    connector = aiohttp.TCPConnector(limit=SCAN_BATCH_SIZE, force_close=True)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Scan in batches to avoid overwhelming the network
        for i in range(0, len(all_ips), SCAN_BATCH_SIZE):
            batch = all_ips[i:i + SCAN_BATCH_SIZE]
            
            tasks = [
                check_sonos_device(session, ip, timeout)
                for ip in batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ip, result in zip(batch, results):
                if isinstance(result, dict) and result:
                    _LOGGER.info("Found Sonos device at %s: %s", ip, result.get("zone_name", "Unknown"))
                    discovered_devices.append(result)
    
    return discovered_devices


async def validate_sonos_ip(
    hass: HomeAssistant,
    ip_address: str,
    timeout: int = DEFAULT_SCAN_TIMEOUT,
) -> dict[str, Any] | None:
    """Validate that a Sonos device exists at the given IP."""
    try:
        # Validate IP format
        IPv4Address(ip_address)
    except ValueError:
        _LOGGER.error("Invalid IP address format: %s", ip_address)
        return None
    
    async with aiohttp.ClientSession() as session:
        return await get_speaker_info(session, ip_address, timeout)


async def quick_ping_check(ip: str, port: int = SONOS_PORT, timeout: float = 1.0) -> bool:
    """Quick check if a port is open on an IP address."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False
