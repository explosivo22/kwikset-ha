"""Base entity class for Kwikset entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN as KWIKSET_DOMAIN
from .device import KwiksetDeviceDataUpdateCoordinator


class KwiksetEntity(CoordinatorEntity[KwiksetDeviceDataUpdateCoordinator]):
    """A base class for Kwikset entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entity_type: str,
        name: str,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        **kwargs,
    ) -> None:
        """Init Kwikset entity."""
        super().__init__(coordinator)
        
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{entity_type}"
        self._device = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(KWIKSET_DOMAIN, self._device.device_id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name,
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success