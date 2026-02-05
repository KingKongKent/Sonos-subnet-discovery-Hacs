"""Config flow for Sonos Subnet Discovery integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_SPEAKER_IPS,
    CONF_SCAN_SUBNET,
    CONF_SCAN_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
)
from .discovery import validate_sonos_ip, scan_subnet_for_sonos

_LOGGER = logging.getLogger(__name__)


class SonosSubnetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonos Subnet Discovery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: list[dict[str, Any]] = []
        self._speaker_ips: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["manual", "scan"],
            description_placeholders={
                "manual": "Enter IP addresses manually",
                "scan": "Scan a subnet for devices",
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual IP entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_addresses = user_input.get(CONF_SPEAKER_IPS, "")
            
            # Parse comma-separated IPs
            ips = [ip.strip() for ip in ip_addresses.split(",") if ip.strip()]
            
            if not ips:
                errors["base"] = "no_ips"
            else:
                # Validate each IP
                valid_ips: list[str] = []
                invalid_ips: list[str] = []
                
                for ip in ips:
                    speaker_info = await validate_sonos_ip(self.hass, ip)
                    if speaker_info:
                        valid_ips.append(ip)
                        self._discovered_devices.append(speaker_info)
                    else:
                        invalid_ips.append(ip)
                
                if invalid_ips:
                    _LOGGER.warning("Could not find Sonos devices at: %s", ", ".join(invalid_ips))
                
                if valid_ips:
                    self._speaker_ips = valid_ips
                    return await self.async_step_confirm()
                else:
                    errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_SPEAKER_IPS): str,
            }),
            errors=errors,
            description_placeholders={
                "example": "192.168.2.100, 192.168.2.101",
            },
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle subnet scanning."""
        errors: dict[str, str] = {}

        if user_input is not None:
            subnet = user_input.get(CONF_SCAN_SUBNET, "")
            timeout = user_input.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT)
            
            if not subnet:
                errors["base"] = "invalid_subnet"
            else:
                # Scan the subnet
                self._discovered_devices = await scan_subnet_for_sonos(
                    self.hass, subnet, timeout
                )
                
                if self._discovered_devices:
                    self._speaker_ips = [
                        d["ip_address"] for d in self._discovered_devices
                    ]
                    return await self.async_step_select_devices()
                else:
                    errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_SUBNET): str,
                vol.Optional(CONF_SCAN_TIMEOUT, default=DEFAULT_SCAN_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=30)
                ),
            }),
            errors=errors,
            description_placeholders={
                "example": "192.168.2.0/24",
            },
        )

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow user to select which devices to add."""
        if user_input is not None:
            selected_ips = user_input.get("selected_devices", [])
            if selected_ips:
                self._speaker_ips = selected_ips
                return await self.async_step_confirm()

        # Build device selection options
        device_options = {
            device["ip_address"]: f"{device.get('zone_name', 'Unknown')} ({device['ip_address']}) - {device.get('model_name', 'Unknown')}"
            for device in self._discovered_devices
        }

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema({
                vol.Required("selected_devices", default=list(device_options.keys())): cv.multi_select(device_options),
            }),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the configuration."""
        if user_input is not None:
            # Create unique ID based on first speaker
            if self._discovered_devices:
                first_device = self._discovered_devices[0]
                unique_id = first_device.get("uuid") or first_device.get("serial_number") or first_device["ip_address"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Sonos Subnet ({len(self._speaker_ips)} devices)",
                data={
                    CONF_SPEAKER_IPS: self._speaker_ips,
                },
            )

        # Show summary of devices to be added
        device_list = []
        for device in self._discovered_devices:
            if device["ip_address"] in self._speaker_ips:
                device_list.append(
                    f"• {device.get('zone_name', 'Unknown')} ({device['ip_address']})"
                )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_count": str(len(self._speaker_ips)),
                "device_list": "\n".join(device_list) if device_list else "No devices",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SonosSubnetOptionsFlow(config_entry)


class SonosSubnetOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Sonos Subnet Discovery."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._new_devices: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_device", "remove_device", "scan_subnet"],
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_address = user_input.get("ip_address", "").strip()
            
            if ip_address:
                speaker_info = await validate_sonos_ip(self.hass, ip_address)
                if speaker_info:
                    current_ips = list(self.config_entry.data.get(CONF_SPEAKER_IPS, []))
                    if ip_address not in current_ips:
                        current_ips.append(ip_address)
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            data={**self.config_entry.data, CONF_SPEAKER_IPS: current_ips},
                        )
                        return self.async_create_entry(title="", data={})
                    else:
                        errors["base"] = "already_configured"
                else:
                    errors["base"] = "no_device_found"
            else:
                errors["base"] = "invalid_ip"

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema({
                vol.Required("ip_address"): str,
            }),
            errors=errors,
        )

    async def async_step_remove_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a device."""
        current_ips = list(self.config_entry.data.get(CONF_SPEAKER_IPS, []))

        if user_input is not None:
            ip_to_remove = user_input.get("ip_address")
            if ip_to_remove and ip_to_remove in current_ips:
                current_ips.remove(ip_to_remove)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_SPEAKER_IPS: current_ips},
                )
            return self.async_create_entry(title="", data={})

        device_options = {ip: ip for ip in current_ips}

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({
                vol.Required("ip_address"): vol.In(device_options),
            }),
        )

    async def async_step_scan_subnet(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Scan subnet for new devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            subnet = user_input.get(CONF_SCAN_SUBNET, "")
            timeout = user_input.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT)
            
            if subnet:
                discovered = await scan_subnet_for_sonos(self.hass, subnet, timeout)
                current_ips = set(self.config_entry.data.get(CONF_SPEAKER_IPS, []))
                
                # Filter out already configured devices
                self._new_devices = [
                    d for d in discovered if d["ip_address"] not in current_ips
                ]
                
                if self._new_devices:
                    return await self.async_step_select_new_devices()
                else:
                    errors["base"] = "no_new_devices"
            else:
                errors["base"] = "invalid_subnet"

        return self.async_show_form(
            step_id="scan_subnet",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_SUBNET): str,
                vol.Optional(CONF_SCAN_TIMEOUT, default=DEFAULT_SCAN_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=30)
                ),
            }),
            errors=errors,
        )

    async def async_step_select_new_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select new devices to add."""
        if user_input is not None:
            selected_ips = user_input.get("selected_devices", [])
            if selected_ips:
                current_ips = list(self.config_entry.data.get(CONF_SPEAKER_IPS, []))
                current_ips.extend(selected_ips)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_SPEAKER_IPS: current_ips},
                )
            return self.async_create_entry(title="", data={})

        device_options = {
            device["ip_address"]: f"{device.get('zone_name', 'Unknown')} ({device['ip_address']})"
            for device in self._new_devices
        }

        return self.async_show_form(
            step_id="select_new_devices",
            data_schema=vol.Schema({
                vol.Required("selected_devices", default=list(device_options.keys())): cv.multi_select(device_options),
            }),
        )
