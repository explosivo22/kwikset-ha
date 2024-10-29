"""Support for locks through the Kwikset API."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as KWIKSET_DOMAIN, LOGGER
from .device import KwiksetDeviceDataUpdateCoordinator
from .entity import KwiksetEntity

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kwikset lock from config entry."""
    devices: list[KwiksetDeviceDataUpdateCoordinator] = hass.data[KWIKSET_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.append(KwiksetLock(device, config_entry.options))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

class KwiksetLock(KwiksetEntity, LockEntity):
    """Define a Kwikset lock."""

    def __init__(self, device: KwiksetDeviceDataUpdateCoordinator, options) -> None:
        """Initialize the lock heater."""
        super().__init__("lock",device.device_name,device)
        self.options = options

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._device.lock()
        self._state = LockState.LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self._device.unlock()
        self._state = LockState.UNLOCKED
        self.async_write_ha_state()

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._device.status == "Locked"

    @callback
    def _async_update_state(self) -> None:
        """Handle updated data from the coordinator."""
        
        if self._device.status == "Locked":
            self._attr_is_locked = True
        elif self._device.status == "Unlocked":
            self._attr_is_locked = False
        
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self._async_update_state))
