"""Support for Kwikset smart lock entities.

This module provides lock entities for Kwikset smart locks.
Each physical lock device is represented as a LockEntity that supports:
    - Lock/unlock actions via the coordinator
    - Real-time locked/unlocked state from API polling

Architecture:
    - Uses translation_key for entity naming (Platinum tier compliance)
    - All actions delegate to the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold tier compliance)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# PARALLEL_UPDATES imported from const.py - limits concurrent API calls


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset lock entities from a config entry."""
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add lock entities for newly discovered devices."""
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

        async_add_entities(
            KwiksetLock(devices[device_id]) for device_id in new_ids
        )
        known_ids.update(new_ids)
        LOGGER.debug("Added lock entities for devices: %s", new_ids)

    # Add existing devices
    _async_add_new_devices()

    # Listen for new device discovery events
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetLock(KwiksetEntity, LockEntity):
    """Kwikset smart lock entity.

    Provides lock/unlock control and state monitoring.
    Uses translation_key for entity naming per Platinum tier requirements.
    """

    _attr_translation_key = "lock"

    def __init__(self, coordinator: KwiksetDeviceDataUpdateCoordinator) -> None:
        """Initialize the lock entity."""
        super().__init__("lock", coordinator)

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked, None if unknown."""
        status = self.coordinator.status
        if status == "Unknown":
            return None
        return status == "Locked"

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device via coordinator.

        Raises:
            HomeAssistantError: If the lock operation fails.
        """
        try:
            await self.coordinator.lock()
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_failed",
            ) from err

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device via coordinator.

        Raises:
            HomeAssistantError: If the unlock operation fails.
        """
        try:
            await self.coordinator.unlock()
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
            ) from err
