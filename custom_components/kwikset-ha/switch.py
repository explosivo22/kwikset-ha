"""Support for Kwikset Smart lock sensors."""
from __future__ import annotations

from homeassistant.components.switch import (
    SwitchEntity,
)

from homeassistant.core import callback

from homeassistant.const import (
    PERCENTAGE
)

from .const import DOMAIN as KWIKSET_DOMAIN, LOGGER
from .device import KwiksetDeviceDataUpdateCoordinator
from .entity import KwiksetEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kwikset sensors from config entry."""
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = hass.data[KWIKSET_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    
    known_device_ids: set[str] = set()
    
    @callback
    def _add_new_devices() -> None:
        """Add new switch entities for newly discovered devices."""
        entities = []
        current_device_ids = set(devices.keys())
        new_device_ids = current_device_ids - known_device_ids
        
        for device_id in new_device_ids:
            device = devices[device_id]
            entities.extend([
                KwiksetLEDSwitch(device),
                KwiksetAudioSwitch(device),
                KwiksetSecureScreenSwitch(device),
            ])
            known_device_ids.add(device_id)
            LOGGER.debug("Added new switch entities for device: %s", device_id)
        
        if entities:
            async_add_entities(entities)
    
    # Add existing devices
    _add_new_devices()
    
    # Listen for new devices - this callback will be triggered during reload
    # when new devices are discovered
    config_entry.async_on_unload(
        hass.bus.async_listen(
            f"{KWIKSET_DOMAIN}_new_device",
            lambda event: _add_new_devices()
        )
    )

class KwiksetLEDSwitch(KwiksetEntity, SwitchEntity):
    """Control the LED status of the lock."""

    def __init__(self, device):
        """Initialize the LED switch."""
        super().__init__("led_switch", f"{device.device_name} LED", device)

    @property
    def is_on(self) -> bool | None:
        """Return true if LED is on."""
        return self.coordinator.led_status

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the LED on."""
        await self.coordinator.set_led(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the LED off."""
        await self.coordinator.set_led(False)

class KwiksetAudioSwitch(KwiksetEntity, SwitchEntity):
    """Control the audio status of the lock."""

    def __init__(self, device):
        """Initialize the audio switch."""
        super().__init__("audio_switch", f"{device.device_name} Audio", device)

    @property
    def is_on(self) -> bool | None:
        """Return true if audio is on."""
        return self.coordinator.audio_status
    
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the audio on."""
        await self.coordinator.set_audio(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the audio off."""
        await self.coordinator.set_audio(False)

class KwiksetSecureScreenSwitch(KwiksetEntity, SwitchEntity):
    """Control the secure screen status of the lock."""

    def __init__(self, device):
        """Initialize the secure screen switch."""
        super().__init__("secure_screen_switch", f"{device.device_name} Secure Screen", device)

    @property
    def is_on(self) -> bool | None:
        """Return true if secure screen is on."""
        return self.coordinator.secure_screen_status

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the secure screen on."""
        await self.coordinator.set_secure_screen(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the secure screen off."""
        await self.coordinator.set_secure_screen(False)