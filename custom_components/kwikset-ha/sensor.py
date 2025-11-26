"""Support for Kwikset smart lock sensors.

This module provides sensor entities for Kwikset smart locks.
Currently supports:
    - Battery percentage sensor (diagnostic category)

Architecture:
    - Uses translation_key for entity naming (Platinum tier compliance)
    - All state is retrieved from the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold tier compliance)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Limit concurrent API calls to prevent rate limiting
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset sensor entities from a config entry."""
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add sensor entities for newly discovered devices."""
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

        async_add_entities(
            KwiksetBatterySensor(devices[device_id]) for device_id in new_ids
        )
        known_ids.update(new_ids)
        LOGGER.debug("Added sensor entities for devices: %s", new_ids)

    # Add existing devices
    _async_add_new_devices()

    # Listen for new device discovery events
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetBatterySensor(KwiksetEntity, SensorEntity):
    """Battery percentage sensor for a Kwikset lock.

    Reports battery level (0-100%) as a diagnostic sensor.
    Uses translation_key for entity naming per Platinum tier requirements.
    """

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: KwiksetDeviceDataUpdateCoordinator) -> None:
        """Initialize the battery sensor."""
        super().__init__("battery", coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the current battery percentage."""
        return self.coordinator.battery_percentage