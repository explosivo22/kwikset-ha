"""Support for Kwikset smart lock entities.

This module provides lock entities for Kwikset smart locks.
Each physical lock device is represented as a LockEntity that supports:
    - Lock/unlock actions via the coordinator
    - Real-time locked/unlocked state from API polling

Architecture:
    - Uses translation_key for entity naming (Bronze: has_entity_name)
    - All actions delegate to the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold: dynamic_devices)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud

Quality Scale Compliance:
    Bronze tier:
        - has_entity_name: Uses translation_key for entity naming
        - entity_unique_id: Inherited from KwiksetEntity base class

    Silver tier:
        - parallel_updates: PARALLEL_UPDATES = 1 limits concurrent API calls
        - action_exceptions: Raises HomeAssistantError with translation_key
        - entity_unavailable: Inherited from KwiksetEntity.available

    Gold tier:
        - dynamic_devices: Listens for "{DOMAIN}_new_device" bus events

Entity Pattern:
    The lock entity follows the coordinator-centric pattern:
    1. State is read from coordinator.status property
    2. Actions (lock/unlock) call coordinator methods
    3. Coordinator handles API calls, retries, and token refresh
    4. Coordinator triggers refresh after successful actions

Error Handling:
    Lock/unlock operations can fail due to:
    - Network connectivity issues
    - API rate limiting
    - Device offline
    - Authentication issues (handled by coordinator)
    
    Failures are wrapped in HomeAssistantError with translation keys
    for user-friendly error messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .const import PARALLEL_UPDATES as _PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates
# Module-level declaration required by HA to limit concurrent API calls to 1
# This prevents overwhelming the Kwikset cloud service with simultaneous requests
# Each lock action (lock/unlock) is serialized at the platform level
PARALLEL_UPDATES: int = _PARALLEL_UPDATES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset lock entities from a config entry.

    Gold tier: dynamic_devices
    This function implements dynamic device discovery by:
    1. Adding entities for devices discovered during setup
    2. Listening for "{DOMAIN}_new_device" bus events
    3. Automatically adding entities when new devices are discovered

    The callback pattern ensures thread-safe entity addition from
    both initial setup and runtime discovery events.

    Args:
        hass: Home Assistant instance
        entry: Config entry being set up
        async_add_entities: Callback to add entities to HA
    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add lock entities for newly discovered devices.

        Gold tier: dynamic_devices
        This callback is called:
        1. During initial setup (for existing devices)
        2. When "{DOMAIN}_new_device" event is fired (for runtime discoveries)

        The known_ids set prevents duplicate entity creation.
        """
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
    # Gold tier: dynamic_devices - runtime discovery support
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetLock(KwiksetEntity, LockEntity):
    """Kwikset smart lock entity.

    Provides lock/unlock control and state monitoring for a Kwikset smart lock.
    
    Quality Scale Implementation:
        Bronze - has_entity_name:
            Uses _attr_translation_key = "lock" which maps to
            entity.lock.lock.name in strings.json → "Lock"
        
        Bronze - entity_unique_id:
            Inherited from KwiksetEntity: {device_id}_lock
        
        Silver - action_exceptions:
            async_lock/async_unlock raise HomeAssistantError
            with translation_key for user-friendly messages
        
        Silver - entity_unavailable:
            Inherited from KwiksetEntity.available property

    State Mapping:
        coordinator.status → is_locked:
        - "Locked" → True
        - "Unlocked" → False
        - "Unknown" → None
    """

    # Bronze tier: has_entity_name
    # Translation key maps to entity.lock.lock.name in strings.json
    _attr_translation_key = "lock"

    def __init__(self, coordinator: KwiksetDeviceDataUpdateCoordinator) -> None:
        """Initialize the lock entity.

        Args:
            coordinator: Device coordinator for this lock
        """
        # Bronze tier: entity_unique_id via parent class
        # Creates unique_id: {device_id}_lock
        super().__init__("lock", coordinator)

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked, None if unknown.

        Reads state from coordinator (never API directly).
        The coordinator polls the API and caches the state.

        Returns:
            True if locked, False if unlocked, None if unknown
        """
        status = self.coordinator.status
        if status == "Unknown":
            return None
        return status == "Locked"

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device via coordinator.

        Silver tier: action_exceptions
        Delegates to coordinator.lock() which handles:
        - Token validation and refresh
        - API call with retry logic
        - Error categorization (auth vs transient)

        Raises:
            HomeAssistantError: If the lock operation fails.
                Uses translation_key for user-friendly message.
        """
        try:
            await self.coordinator.lock()
        except Exception as err:
            # Silver tier: action_exceptions with translation_key
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_failed",
            ) from err

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device via coordinator.

        Silver tier: action_exceptions
        Delegates to coordinator.unlock() which handles:
        - Token validation and refresh
        - API call with retry logic
        - Error categorization (auth vs transient)

        Raises:
            HomeAssistantError: If the unlock operation fails.
                Uses translation_key for user-friendly message.
        """
        try:
            await self.coordinator.unlock()
        except Exception as err:
            # Silver tier: action_exceptions with translation_key
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
            ) from err
