"""Support for Kwikset Smart lock sensors."""
from __future__ import annotations

from homeassistant.components.switch import (
    SwitchEntity,
)

from homeassistant.const import (
    PERCENTAGE
)

from .const import DOMAIN as KWIKSET_DOMAIN
from .device import KwiksetDeviceDataUpdateCoordinator
from .entity import KwiksetEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kwikset sensors from config entry."""
    coordinator: KwiksetDeviceDataUpdateCoordinator = hass.data[KWIKSET_DOMAIN][config_entry.entry_id]

    devices: list[KwiksetDeviceDataUpdateCoordinator] = hass.data[KWIKSET_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.extend(
            [
                KwiksetLEDSwitch(device),
                KwiksetAudioSwitch(device),
                KwiksetSecureScreenSwitch(device),
            ]
        )
    async_add_entities(entities)

class KwiksetLEDSwitch(KwiksetEntity, SwitchEntity):
    """Monitors the temperature."""

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("led_switch", f"{device.device_name} LED", device)
        self._state: float = None

    @property
    def is_on(self):
        return self._device.led_status

    async def async_turn_on(self, **kwargs) -> None:
        await self._device.set_led("true")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.set_led("false")

        self.async_write_ha_state()

class KwiksetAudioSwitch(KwiksetEntity, SwitchEntity):
    """Monitors the temperature."""

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("audio_switch", f"{device.device_name} Audio", device)
        self._state: float = None

    @property
    def is_on(self):
        return self._device.audio_status
    
    async def async_turn_on(self, **kwargs) -> None:
        await self._device.set_audio("true")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.set_audio("false")

        self.async_write_ha_state()

class KwiksetSecureScreenSwitch(KwiksetEntity, SwitchEntity):
    """Monitors the temperature."""

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("secure_screen_switch", f"{device.device_name} Secure Screen", device)
        self._state: float = None

    @property
    def is_on(self):
        return self._device.secure_screen_status

    async def async_turn_on(self, **kwargs) -> None:
        await self._device.set_secure_screen("true")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.set_secure_screen("false")

        self.async_write_ha_state()