"""Base entity class for Kwikset entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as KWIKSET_DOMAIN
from .device import KwiksetDeviceDataUpdateCoordinator

class KwiksetEntity(Entity):
    """A base class for Kwikset entities."""

    _attr_force_update = False
    _attr_should_poll = True
    
    def __init__(
        self,
        entity_type: str,
        name: str,
        device: KwiksetDeviceUpdateCoordinator,
        **kwargs,
    ) -> None:
        """Init Kwikset entity."""
        self._attr_name = name
        self._attr_unique_id = f"{device.id}_{entity_type}"

        self._device: KwiksetDeviceDataUpdateCoordinator = device
        self._state: Any = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(KWIKSET_DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name,
            serial=self._device.serial_number,
            sw_version=self._device.firmware_version,
        )
    
    async def async_update(self):
        """Update Kwikset entity."""
        await self._device.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass"""
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))