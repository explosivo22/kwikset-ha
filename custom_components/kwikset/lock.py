"""Support for Kwikset smart lock entities.

This module provides the primary lock entity for Kwikset smart locks.
Each physical lock device exposes a single LockEntity that supports:
    - Lock/unlock actions via the coordinator
    - Real-time locked/unlocked state from API polling
    - Optimistic locking/unlocking states with timeout

Architecture:
    - Single entity per device (no EntityDescription pattern needed)
    - Uses _attr_name = None for primary device entity (HA convention)
    - All actions delegate to coordinator (coordinator-centric design)
    - Dynamic device discovery via bus events (Gold: dynamic_devices)
    - PARALLEL_UPDATES = 1 prevents rate limiting
    - Optimistic state with timeout for responsive UI

Quality Scale Compliance:
    Bronze: has_entity_name, entity_unique_id (via KwiksetEntity)
    Silver: parallel_updates, action_exceptions, entity_unavailable
    Gold: dynamic_devices via bus events
    Platinum: strict_typing, __slots__ for memory efficiency

Coordinator Pattern:
    State: coordinator.status → LockState enum
    Actions: coordinator.lock() / coordinator.unlock()
    The coordinator handles API calls, retries, and token refresh.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .const import LOGGER
from .const import OPTIMISTIC_TIMEOUT_SECONDS
from .const import PARALLEL_UPDATES as _PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates - serialize API calls per platform
PARALLEL_UPDATES: int = _PARALLEL_UPDATES

# Map coordinator status strings to HA LockState for type safety
_STATUS_TO_LOCKED: dict[str, bool | None] = {
    "Locked": True,
    "Unlocked": False,
    "Unknown": None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset lock entities from a config entry.

    Gold tier: dynamic_devices - supports runtime device discovery.
    Uses callback pattern for thread-safe entity addition.
    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add lock entities for newly discovered devices."""
        if new_ids := set(devices.keys()) - known_ids:
            async_add_entities(KwiksetLock(devices[d]) for d in new_ids)
            known_ids.update(new_ids)
            LOGGER.debug("Added lock entities for devices: %s", new_ids)

    _async_add_new_devices()

    # Gold tier: dynamic_devices - listen for runtime discoveries
    entry.async_on_unload(
        hass.bus.async_listen(
            f"{DOMAIN}_new_device", lambda _: _async_add_new_devices()
        )
    )


class KwiksetLock(KwiksetEntity, LockEntity):
    """Kwikset smart lock entity.

    Provides lock/unlock control and state for a Kwikset smart lock.
    This is the primary entity for each device, following HA conventions:
    - _attr_name = None: Entity uses device name directly
    - _attr_translation_key: For entity-specific translations
    - Uses optimistic locking/unlocking states with timeout

    Optimistic State Pattern:
        When lock/unlock is called, we immediately set is_locking/is_unlocking
        to True and write state. This provides instant UI feedback.
        A timer resets the optimistic state after OPTIMISTIC_TIMEOUT_SECONDS
        if the coordinator doesn't provide an update sooner.
        When coordinator update arrives, we reset the optimistic state.

    Quality Scale:
        Bronze: has_entity_name, entity_unique_id (via base class)
        Silver: action_exceptions with translation_key
        Platinum: __slots__ for memory efficiency
    """

    # Platinum tier: __slots__ reduces memory footprint
    __slots__ = ("_optimistic_timer",)

    # Bronze tier: has_entity_name - entity is the primary device entity
    # Setting name to None means the entity will use the device name
    _attr_name: str | None = None
    _attr_translation_key = "lock"

    def __init__(self, coordinator: KwiksetDeviceDataUpdateCoordinator) -> None:
        """Initialize the lock entity."""
        super().__init__("lock", coordinator)
        self._optimistic_timer: asyncio.TimerHandle | None = None
        # Set initial lock state from coordinator
        self._update_lock_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        When the coordinator provides new data, reset any optimistic state
        since we now have the actual state from the device.
        """
        # Reset optimistic state without writing (we'll write below)
        self._reset_optimistic_state(write_state=False)
        self._update_lock_state()
        super()._handle_coordinator_update()

    def _update_lock_state(self) -> None:
        """Update the is_locked state from coordinator data."""
        self._attr_is_locked = _STATUS_TO_LOCKED.get(self.coordinator.status)

    @callback
    def _reset_optimistic_state(self, write_state: bool = True) -> None:
        """Reset the optimistic locking/unlocking state.

        Called when:
        - Coordinator provides actual device state
        - Optimistic timeout expires
        - Entity is being removed

        Args:
            write_state: Whether to write state to HA after reset.

        """
        if self._optimistic_timer and not self._optimistic_timer.cancelled():
            self._optimistic_timer.cancel()
        self._optimistic_timer = None
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        if write_state:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is being removed."""
        self._reset_optimistic_state(write_state=False)
        await super().async_will_remove_from_hass()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device.

        Implements optimistic state pattern:
        1. If not already locked, set is_locking = True for immediate UI feedback
        2. Start a timer to reset optimistic state if coordinator doesn't update
        3. Send lock command to coordinator
        4. Request coordinator refresh to get actual state

        Silver tier: action_exceptions with translation_key for i18n.
        """
        if not self._attr_is_locked:
            # Optimistically signal locking to state machine
            self._attr_is_locking = True
            self.async_write_ha_state()
            # The lock should acknowledge the command with a state update,
            # but guard against it with a timer in case update doesn't arrive.
            self._optimistic_timer = self.hass.loop.call_later(
                OPTIMISTIC_TIMEOUT_SECONDS, self._reset_optimistic_state
            )
            LOGGER.debug(
                "Optimistically set locking state for %s, timeout in %ds",
                self.entity_id,
                OPTIMISTIC_TIMEOUT_SECONDS,
            )

        try:
            await self.coordinator.lock()
        except Exception as err:
            # Reset optimistic state on error
            self._reset_optimistic_state(write_state=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_failed",
            ) from err

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device.

        Implements optimistic state pattern:
        1. If currently locked, set is_unlocking = True for immediate UI feedback
        2. Start a timer to reset optimistic state if coordinator doesn't update
        3. Send unlock command to coordinator
        4. Request coordinator refresh to get actual state

        Silver tier: action_exceptions with translation_key for i18n.
        """
        if self._attr_is_locked:
            # Optimistically signal unlocking to state machine
            self._attr_is_unlocking = True
            self.async_write_ha_state()
            # The lock should acknowledge the command with a state update,
            # but guard against it with a timer in case update doesn't arrive.
            self._optimistic_timer = self.hass.loop.call_later(
                OPTIMISTIC_TIMEOUT_SECONDS, self._reset_optimistic_state
            )
            LOGGER.debug(
                "Optimistically set unlocking state for %s, timeout in %ds",
                self.entity_id,
                OPTIMISTIC_TIMEOUT_SECONDS,
            )

        try:
            await self.coordinator.unlock()
        except Exception as err:
            # Reset optimistic state on error
            self._reset_optimistic_state(write_state=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
            ) from err
