"""Support for Kwikset smart lock event entities.

Fires an HA event each time a lock/unlock/jam event is detected via
the coordinator's history polling. Shows in the HA logbook with full
event metadata and can trigger automations.

Quality Scale:
    Bronze: has_entity_name, entity_unique_id (via KwiksetEntity)
    Silver: parallel_updates, entity_unavailable (via KwiksetEntity)
    Gold: dynamic_devices via bus events, entity_category, entity_translations
    Platinum: strict_typing, __slots__
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .const import LOGGER
from .const import PARALLEL_UPDATES as _PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates — serialize API calls per platform
PARALLEL_UPDATES: int = _PARALLEL_UPDATES

# Event type constants (lowercase per HA EventEntity convention)
EVENT_LOCKED: str = "locked"
EVENT_UNLOCKED: str = "unlocked"
EVENT_JAMMED: str = "jammed"

# Map API event names (title case) to event types (lowercase)
_EVENT_MAP: dict[str, str] = {
    "Locked": EVENT_LOCKED,
    "Unlocked": EVENT_UNLOCKED,
    "Jammed": EVENT_JAMMED,
}

# Sentinel for "no event seen yet" — distinct from any real API event ID.
# Using -1 instead of None allows the first real event (including those
# synthesized from websocket data) to always trigger.
_UNSET_EVENT_ID: int = -1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset event entities from a config entry.

    Gold tier: dynamic_devices — supports runtime device discovery.
    Creates a KwiksetLockEvent for each lock device.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.
        async_add_entities: Callback to add entities to HA.

    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add event entities for newly discovered devices."""
        if new_ids := set(devices.keys()) - known_ids:
            async_add_entities(KwiksetLockEvent(devices[d]) for d in new_ids)
            known_ids.update(new_ids)
            LOGGER.debug("Added event entities for devices: %s", new_ids)

    _async_add_new_devices()

    # Gold tier: dynamic_devices — listen for runtime discoveries
    entry.async_on_unload(
        hass.bus.async_listen(
            f"{DOMAIN}_new_device", lambda _: _async_add_new_devices()
        )
    )


class KwiksetLockEvent(KwiksetEntity, EventEntity):
    """Event entity that fires on lock/unlock/jammed events.

    Detects new events by comparing the latest event's ID from the
    coordinator history against the previously seen event ID. When a
    new event is detected, _trigger_event fires with the event type
    and attributes containing user, event_type, timestamp, etc.

    The initial event ID is seeded during __init__ so the first
    coordinator update does not spuriously fire an event.

    MRO: KwiksetLockEvent → KwiksetEntity → CoordinatorEntity → EventEntity
         → RestoreEntity → Entity
    This is the same pattern used by Ring, Overseerr, and other HA core
    integrations that combine CoordinatorEntity with EventEntity.

    Quality Scale:
        Bronze: has_entity_name, entity_unique_id (via KwiksetEntity)
        Silver: entity_unavailable (via KwiksetEntity)
        Platinum: __slots__ for memory efficiency, strict_typing
    """

    __slots__ = ("_last_event_id",)

    # No EventDeviceClass.LOCK exists — omit device_class (stays None)
    _attr_event_types: ClassVar[list[str]] = [
        EVENT_LOCKED,
        EVENT_UNLOCKED,
        EVENT_JAMMED,
    ]
    _attr_translation_key = "lock_event"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
    ) -> None:
        """Initialize the event entity.

        Seeds _last_event_id from the coordinator's current latest event
        to avoid firing a stale event on the first coordinator update
        after HA startup.

        Args:
            coordinator: Device coordinator for this lock.

        """
        super().__init__("lock_event", coordinator)
        # Seed with the current latest event ID so the first coordinator
        # update (same data) does not spuriously fire.  When no history
        # is available, the sentinel _UNSET_EVENT_ID ensures the very
        # first real event (API or websocket-synthesized) will fire.
        events = coordinator.history_events
        self._last_event_id: int = (
            events[0].get("id", _UNSET_EVENT_ID) if events else _UNSET_EVENT_ID
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Compares the latest event ID against the previously seen ID.
        If different and we have a previous ID (not initial load),
        fires a new event via _trigger_event.

        Must call _trigger_event() BEFORE super()._handle_coordinator_update()
        because the parent calls async_write_ha_state(), which reads the
        internal event state set by _trigger_event().
        """
        events = self.coordinator.history_events
        if not events:
            super()._handle_coordinator_update()
            return

        latest = events[0]
        latest_id = latest.get("id")

        if latest_id != self._last_event_id:
            # New event detected — map API event name to our event type
            raw_event = latest.get("event", "")
            event_type = _EVENT_MAP.get(raw_event, EVENT_LOCKED)

            self._trigger_event(
                event_type,
                {
                    "user": latest.get("user"),
                    "event_type": latest.get("eventtype"),
                    "timestamp": latest.get("timestamp"),
                    "event_category": latest.get("eventcategory"),
                    "device_name": latest.get("devicename"),
                },
            )
            LOGGER.debug(
                "Lock event fired for %s: %s by %s",
                self.coordinator.device_name,
                event_type,
                latest.get("user"),
            )

        self._last_event_id = latest_id
        super()._handle_coordinator_update()
