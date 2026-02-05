"""Switch platform for Sonos Subnet Discovery."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONTROL_AV_TRANSPORT,
    CONTROL_RENDERING,
    CONTROL_DEVICE_PROPERTIES,
    UPNP_AV_TRANSPORT,
    UPNP_RENDERING_CONTROL,
    UPNP_DEVICE_PROPERTIES,
)
from .coordinator import SonosSubnetCoordinator
from .helpers import send_upnp_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos switch entities from a config entry."""
    coordinator: SonosSubnetCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    for ip, speaker_info in coordinator.speakers.items():
        entities.append(SonosCrossfadeSwitch(coordinator, ip, speaker_info))
        entities.append(SonosLoudnessSwitch(coordinator, ip, speaker_info))
        entities.append(SonosStatusLightSwitch(coordinator, ip, speaker_info))
        entities.append(SonosTouchControlsSwitch(coordinator, ip, speaker_info))
        # Night mode and Speech Enhancement are only for soundbars
        entities.append(SonosNightModeSwitch(coordinator, ip, speaker_info))
        entities.append(SonosSpeechEnhancementSwitch(coordinator, ip, speaker_info))

    async_add_entities(entities)


class SonosBaseSwitch(CoordinatorEntity[SonosSubnetCoordinator], SwitchEntity):
    """Base class for Sonos switch entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
        key: str,
        name: str,
        icon_on: str = "mdi:toggle-switch",
        icon_off: str = "mdi:toggle-switch-off",
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        
        self._ip_address = ip_address
        self._speaker_info = speaker_info
        self._key = key
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._base_unique_id = speaker_info.get("uuid") or speaker_info.get("serial_number") or ip_address
        
        self._attr_unique_id = f"{self._base_unique_id}_{key}"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._base_unique_id)},
            name=self._speaker_info.get("zone_name", f"Sonos ({self._ip_address})"),
            manufacturer="Sonos",
            model=self._speaker_info.get("model_name", "Unknown"),
        )

    @property
    def _speaker_data(self) -> dict[str, Any]:
        """Return current speaker data from coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._ip_address, {})
        return {}

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        # Check if the setting exists in the speaker data
        if self._key not in self._speaker_data:
            return False
        return self._speaker_data.get("available", False)

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._speaker_data.get(self._key)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon_on if self.is_on else self._icon_off


class SonosCrossfadeSwitch(SonosBaseSwitch):
    """Crossfade switch for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize crossfade switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="crossfade",
            name="Crossfade",
            icon_on="mdi:swap-horizontal",
            icon_off="mdi:swap-horizontal",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on crossfade."""
        _LOGGER.info("Enabling crossfade on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_AV_TRANSPORT,
            "SetCrossfadeMode",
            "<InstanceID>0</InstanceID><CrossfadeMode>1</CrossfadeMode>",
            CONTROL_AV_TRANSPORT,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off crossfade."""
        _LOGGER.info("Disabling crossfade on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_AV_TRANSPORT,
            "SetCrossfadeMode",
            "<InstanceID>0</InstanceID><CrossfadeMode>0</CrossfadeMode>",
            CONTROL_AV_TRANSPORT,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosLoudnessSwitch(SonosBaseSwitch):
    """Loudness switch for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize loudness switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="loudness",
            name="Loudness",
            icon_on="mdi:volume-vibrate",
            icon_off="mdi:volume-off",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on loudness."""
        _LOGGER.info("Enabling loudness on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetLoudness",
            "<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredLoudness>1</DesiredLoudness>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off loudness."""
        _LOGGER.info("Disabling loudness on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetLoudness",
            "<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredLoudness>0</DesiredLoudness>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosStatusLightSwitch(SonosBaseSwitch):
    """Status light switch for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize status light switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="status_light",
            name="Status Light",
            icon_on="mdi:led-on",
            icon_off="mdi:led-off",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on status light."""
        _LOGGER.info("Enabling status light on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_DEVICE_PROPERTIES,
            "SetLEDState",
            "<DesiredLEDState>On</DesiredLEDState>",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off status light."""
        _LOGGER.info("Disabling status light on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_DEVICE_PROPERTIES,
            "SetLEDState",
            "<DesiredLEDState>Off</DesiredLEDState>",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosTouchControlsSwitch(SonosBaseSwitch):
    """Touch controls switch for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize touch controls switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="touch_controls",
            name="Touch Controls",
            icon_on="mdi:gesture-tap",
            icon_off="mdi:gesture-tap-hold",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable touch controls (unlock buttons)."""
        _LOGGER.info("Enabling touch controls on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_DEVICE_PROPERTIES,
            "SetButtonLockState",
            "<DesiredButtonLockState>Off</DesiredButtonLockState>",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable touch controls (lock buttons)."""
        _LOGGER.info("Disabling touch controls on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_DEVICE_PROPERTIES,
            "SetButtonLockState",
            "<DesiredButtonLockState>On</DesiredButtonLockState>",
            CONTROL_DEVICE_PROPERTIES,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosNightModeSwitch(SonosBaseSwitch):
    """Night mode switch for Sonos soundbars."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize night mode switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="night_mode",
            name="Night Mode",
            icon_on="mdi:weather-night",
            icon_off="mdi:weather-sunny",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on night mode."""
        _LOGGER.info("Enabling night mode on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetEQ",
            "<InstanceID>0</InstanceID><EQType>NightMode</EQType><DesiredValue>1</DesiredValue>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off night mode."""
        _LOGGER.info("Disabling night mode on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetEQ",
            "<InstanceID>0</InstanceID><EQType>NightMode</EQType><DesiredValue>0</DesiredValue>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosSpeechEnhancementSwitch(SonosBaseSwitch):
    """Speech enhancement switch for Sonos soundbars."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize speech enhancement switch."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="speech_enhancement",
            name="Speech Enhancement",
            icon_on="mdi:account-voice",
            icon_off="mdi:account-voice-off",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on speech enhancement."""
        _LOGGER.info("Enabling speech enhancement on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetEQ",
            "<InstanceID>0</InstanceID><EQType>DialogLevel</EQType><DesiredValue>1</DesiredValue>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off speech enhancement."""
        _LOGGER.info("Disabling speech enhancement on %s", self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetEQ",
            "<InstanceID>0</InstanceID><EQType>DialogLevel</EQType><DesiredValue>0</DesiredValue>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()
