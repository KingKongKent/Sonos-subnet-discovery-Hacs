"""Number platform for Sonos Subnet Discovery - EQ Controls."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SONOS_PORT,
    CONTROL_RENDERING,
    UPNP_RENDERING_CONTROL,
)
from .coordinator import SonosSubnetCoordinator
from .helpers import send_upnp_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos number entities from a config entry."""
    coordinator: SonosSubnetCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []

    for ip, speaker_info in coordinator.speakers.items():
        # Add EQ controls
        entities.append(SonosBassNumber(coordinator, ip, speaker_info))
        entities.append(SonosTrebleNumber(coordinator, ip, speaker_info))
        entities.append(SonosBalanceNumber(coordinator, ip, speaker_info))

    async_add_entities(entities)


class SonosBaseNumber(CoordinatorEntity[SonosSubnetCoordinator], NumberEntity):
    """Base class for Sonos number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
        key: str,
        name: str,
        min_value: float,
        max_value: float,
        step: float = 1,
        icon: str = "mdi:tune",
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        
        self._ip_address = ip_address
        self._speaker_info = speaker_info
        self._key = key
        self._base_unique_id = speaker_info.get("uuid") or speaker_info.get("serial_number") or ip_address
        
        self._attr_unique_id = f"{self._base_unique_id}_{key}"
        self._attr_name = name
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_icon = icon

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
        return self._speaker_data.get("available", False)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._speaker_data.get(self._key)


class SonosBassNumber(SonosBaseNumber):
    """Bass control for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize bass number."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="bass",
            name="Bass",
            min_value=-10,
            max_value=10,
            step=1,
            icon="mdi:music-clef-bass",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the bass value."""
        _LOGGER.info("Setting bass to %d on %s", int(value), self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetBass",
            f"<InstanceID>0</InstanceID><DesiredBass>{int(value)}</DesiredBass>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosTrebleNumber(SonosBaseNumber):
    """Treble control for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize treble number."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="treble",
            name="Treble",
            min_value=-10,
            max_value=10,
            step=1,
            icon="mdi:music-clef-treble",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the treble value."""
        _LOGGER.info("Setting treble to %d on %s", int(value), self._ip_address)
        success, _ = await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetTreble",
            f"<InstanceID>0</InstanceID><DesiredTreble>{int(value)}</DesiredTreble>",
            CONTROL_RENDERING,
        )
        if success:
            await self.coordinator.async_request_refresh()


class SonosBalanceNumber(SonosBaseNumber):
    """Balance control for Sonos speakers."""

    def __init__(
        self,
        coordinator: SonosSubnetCoordinator,
        ip_address: str,
        speaker_info: dict[str, Any],
    ) -> None:
        """Initialize balance number."""
        super().__init__(
            coordinator,
            ip_address,
            speaker_info,
            key="balance",
            name="Balance",
            min_value=-100,
            max_value=100,
            step=1,
            icon="mdi:scale-balance",
        )
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        """Return the current balance value.
        
        Balance is calculated from left/right volume difference.
        Negative = left, Positive = right.
        """
        # Balance might not be directly available, return 0 as default
        return self._speaker_data.get("balance", 0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the balance value.
        
        This adjusts the relative volume of left and right channels.
        """
        _LOGGER.info("Setting balance to %d on %s", int(value), self._ip_address)
        
        # Calculate left/right volumes based on balance
        # Balance -100 = full left, 0 = center, +100 = full right
        base_volume = self._speaker_data.get("volume", 50)
        
        if value < 0:
            # Reduce right channel
            left_vol = base_volume
            right_vol = int(base_volume * (100 + value) / 100)
        elif value > 0:
            # Reduce left channel
            left_vol = int(base_volume * (100 - value) / 100)
            right_vol = base_volume
        else:
            left_vol = base_volume
            right_vol = base_volume
        
        # Set left channel volume
        await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetVolume",
            f"<InstanceID>0</InstanceID><Channel>LF</Channel><DesiredVolume>{left_vol}</DesiredVolume>",
            CONTROL_RENDERING,
        )
        
        # Set right channel volume
        await send_upnp_command(
            self._ip_address,
            UPNP_RENDERING_CONTROL,
            "SetVolume",
            f"<InstanceID>0</InstanceID><Channel>RF</Channel><DesiredVolume>{right_vol}</DesiredVolume>",
            CONTROL_RENDERING,
        )
        
        await self.coordinator.async_request_refresh()
