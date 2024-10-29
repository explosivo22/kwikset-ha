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
        self.schedule = options.get('schedule', [])
        self.expiration_date = options.get('expiration_date', None)
        self.expiration_days = options.get('expiration_days', None)

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._device.lock()
        self._state = LockState.LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        if not self._is_within_schedule():
            return
        if self._is_expired():
            return
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

    def _is_within_schedule(self):
        """Check if current time is within the allowed schedule."""
        if not self.schedule:
            return True
        now = datetime.now()
        current_time = now.time()
        current_day = now.strftime("%A")
        for entry in self.schedule:
            if current_day in entry['days']:
                start_time = datetime.strptime(entry['start'], "%H:%M").time()
                end_time = datetime.strptime(entry['end'], "%H:%M").time()
                if start_time <= current_time <= end_time:
                    return True
        return False

    def _is_expired(self):
        """Check if the access has expired."""
        if self.expiration_date:
            if datetime.now() > datetime.strptime(self.expiration_date, "%Y-%m-%d"):
                return True
        if self.expiration_days:
            creation_date = datetime.strptime(self.options.get('creation_date', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
            if (datetime.now() - creation_date).days > self.expiration_days:
                return True
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self._async_update_state))
