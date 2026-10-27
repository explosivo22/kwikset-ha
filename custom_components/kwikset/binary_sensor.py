"""Support for Kwikset smart lock binary sensors.

Provides a diagnostic connectivity sensor that reports whether the lock itself
is reachable (powered and connected), as distinct from the Kwikset cloud being
reachable.  It stays available while the lock is offline so users can see why
the other entities are unavailable.

Quality Scale: Bronze (has_entity_name, entity_unique_id),
Silver (parallel_updates), Gold (dynamic_devices).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .const import LOGGER
from .const import PARALLEL_UPDATES as _PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates - serialize API calls to prevent rate limiting
PARALLEL_UPDATES: int = _PARALLEL_UPDATES


class KwiksetBinarySensorEntityDescription(
    BinarySensorEntityDescription, frozen_or_thawed=True, kw_only=True
):
    """Describes a Kwikset binary sensor entity with a value function."""

    value_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[KwiksetBinarySensorEntityDescription, ...] = (
    KwiksetBinarySensorEntityDescription(
        key="connectivity",
        translation_key="connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.is_online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset binary sensor entities from a config entry.

    Gold tier: dynamic_devices - supports runtime discovery via bus events.
    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add binary sensor entities for newly discovered devices."""
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

        async_add_entities(
            KwiksetBinarySensor(devices[device_id], description)
            for device_id in new_ids
            for description in BINARY_SENSOR_DESCRIPTIONS
        )
        known_ids.update(new_ids)
        LOGGER.debug("Added binary sensor entities for devices: %s", new_ids)

    _async_add_new_devices()

    entry.async_on_unload(
        hass.bus.async_listen(
            f"{DOMAIN}_new_device", lambda _: _async_add_new_devices()
        )
    )


class KwiksetBinarySensor(KwiksetEntity, BinarySensorEntity):
    """Kwikset binary sensor entity driven by an entity description."""

    __slots__ = ()

    entity_description: KwiksetBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        description: KwiksetBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        self.entity_description = description
        super().__init__(description.key, coordinator)

    @property
    def available(self) -> bool:
        """Stay available while the lock is offline; only a cloud failure hides it."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return True when the lock is connected."""
        return self.entity_description.value_fn(self.coordinator)
