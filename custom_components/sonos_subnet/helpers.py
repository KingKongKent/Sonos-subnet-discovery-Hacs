"""Helper functions for Sonos Subnet Discovery."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from xml.sax.saxutils import escape

import aiohttp

from .const import SONOS_PORT

_LOGGER = logging.getLogger(__name__)

# SOAP envelope for UPnP commands
SOAP_ENVELOPE = '''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}:1">{arguments}</u:{action}></s:Body>
</s:Envelope>'''


async def send_upnp_command(
    ip: str,
    service: str,
    action: str,
    arguments: str,
    control_url: str,
    timeout: int = 10,
) -> tuple[bool, str]:
    """Send a UPnP SOAP command to a Sonos speaker.
    
    Returns (success, response_text).
    """
    url = f"http://{ip}:{SONOS_PORT}{control_url}"
    
    soap_body = SOAP_ENVELOPE.format(
        action=action,
        service=service,
        arguments=arguments,
    )
    
    headers = {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPACTION": f'"urn:schemas-upnp-org:service:{service}:1#{action}"',
    }
    
    _LOGGER.debug("Sending UPnP command to %s: %s#%s", url, service, action)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=soap_body.encode('utf-8'),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    _LOGGER.debug("UPnP command %s succeeded for %s", action, ip)
                    return True, response_text
                else:
                    _LOGGER.error(
                        "UPnP command %s failed for %s: HTTP %s - %s",
                        action, ip, response.status, response_text
                    )
                    return False, response_text
    except aiohttp.ClientError as err:
        _LOGGER.error("Connection error sending %s to %s: %s", action, ip, err)
        return False, str(err)
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout sending %s to %s", action, ip)
        return False, "Timeout"
    except Exception as err:
        _LOGGER.exception("Unexpected error sending %s to %s: %s", action, ip, err)
        return False, str(err)


def extract_xml_value(xml_text: str, tag: str) -> str | None:
    """Extract a value from XML text."""
    patterns = [
        rf"<{tag}>([^<]*)</{tag}>",
        rf"<{tag}[^>]*>([^<]*)</{tag}>",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, xml_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return None


def extract_xml_value_int(xml_text: str, tag: str, default: int = 0) -> int:
    """Extract an integer value from XML text."""
    value = extract_xml_value(xml_text, tag)
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return default


def extract_xml_value_bool(xml_text: str, tag: str, default: bool = False) -> bool:
    """Extract a boolean value from XML text."""
    value = extract_xml_value(xml_text, tag)
    if value:
        return value.lower() in ("1", "true", "on", "yes")
    return default


def parse_didl_metadata(didl: str) -> dict[str, Any]:
    """Parse DIDL-Lite metadata from Sonos."""
    metadata = {}
    
    if not didl:
        return metadata
    
    # Unescape HTML entities
    didl = didl.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
    
    # Extract basic track info
    metadata["title"] = extract_xml_value(didl, "dc:title")
    metadata["artist"] = extract_xml_value(didl, "dc:creator")
    metadata["album"] = extract_xml_value(didl, "upnp:album")
    metadata["album_art"] = extract_xml_value(didl, "upnp:albumArtURI")
    
    # Extract streaming radio specific metadata
    metadata["stream_content"] = extract_xml_value(didl, "r:streamContent")
    metadata["radio_show"] = extract_xml_value(didl, "r:radioShowMd")
    
    # If no album art, try alternative fields
    if not metadata["album_art"]:
        metadata["album_art"] = extract_xml_value(didl, "upnp:icon") or extract_xml_value(didl, "albumArtURI")
    
    # Extract duration
    duration_str = extract_xml_value(didl, "res")
    if duration_str:
        duration_match = re.search(r'duration="([^"]+)"', didl)
        if duration_match:
            metadata["duration_str"] = duration_match.group(1)
    
    return metadata


def format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}"


def parse_duration(duration_str: str) -> int:
    """Parse duration string (H:MM:SS or HH:MM:SS) to seconds."""
    if not duration_str:
        return 0
    
    try:
        parts = duration_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    
    return 0


def escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return escape(text) if text else ""
