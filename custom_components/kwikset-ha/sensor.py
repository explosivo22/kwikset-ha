"""Support for Kwikset smart lock sensors.

This module provides sensor entities for Kwikset smart locks.
Currently supports:
    - Battery percentage sensor (diagnostic category)

Architecture:
    - Uses translation_key for entity naming (Bronze: has_entity_name)
    - All state is retrieved from the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold: dynamic_devices)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud

Quality Scale Compliance:
    Bronze tier:
        - has_entity_name: Uses translation_key for entity naming
        - entity_unique_id: Inherited from KwiksetEntity base class

    Silver tier:
        - parallel_updates: PARALLEL_UPDATES = 1 limits concurrent API calls
        - entity_unavailable: Inherited from KwiksetEntity.available

    Gold tier:
        - dynamic_devices: Listens for "{DOMAIN}_new_device" bus events

Entity Categories:
    The battery sensor uses EntityCategory.DIAGNOSTIC because:
    - It provides status information about the device itself
    - It's not a primary control or measurement
    - Users typically don't want it on the main dashboard
    - HA automatically groups diagnostic entities together

Sensor Attributes:
    - SensorDeviceClass.BATTERY: Enables proper HA formatting
    - SensorStateClass.MEASUREMENT: For statistics/history
    - PERCENTAGE unit: Displays as "85%"
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

from .const import DOMAIN, LOGGER, PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates
# PARALLEL_UPDATES imported from const.py - limits concurrent API calls to 1
# While sensors are read-only, this ensures consistent behavior across platforms


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset sensor entities from a config entry.

    Gold tier: dynamic_devices
    This function implements dynamic device discovery by:
    1. Adding entities for devices discovered during setup
    2. Listening for "{DOMAIN}_new_device" bus events
    3. Automatically adding entities when new devices are discovered

    Args:
        hass: Home Assistant instance
        entry: Config entry being set up
        async_add_entities: Callback to add entities to HA
    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add sensor entities for newly discovered devices.

        Gold tier: dynamic_devices
        Creates battery sensor for each new device.
        """
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
    # Gold tier: dynamic_devices - runtime discovery support
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetBatterySensor(KwiksetEntity, SensorEntity):
    """Battery percentage sensor for a Kwikset lock.

    Reports battery level (0-100%) as a diagnostic sensor.

    Quality Scale Implementation:
        Bronze - has_entity_name:
            Uses _attr_translation_key = "battery" which maps to
            entity.sensor.battery.name in strings.json → "Battery"
        
        Bronze - entity_unique_id:
            Inherited from KwiksetEntity: {device_id}_battery
        
        Silver - entity_unavailable:
            Inherited from KwiksetEntity.available property

    Sensor Configuration:
        - device_class: BATTERY for proper HA formatting and icons
        - native_unit: PERCENTAGE for display as "85%"
        - entity_category: DIAGNOSTIC (not a primary measurement)
        - state_class: MEASUREMENT for statistics tracking
    """

    # Bronze tier: has_entity_name
    # Translation key maps to entity.sensor.battery.name in strings.json
    _attr_translation_key = "battery"

    # Sensor configuration for proper HA integration
    _attr_device_class = SensorDeviceClass.BATTERY  # Enables battery icon
    _attr_native_unit_of_measurement = PERCENTAGE   # Display as "85%"
    _attr_entity_category = EntityCategory.DIAGNOSTIC  # Group with diagnostics
    _attr_state_class = SensorStateClass.MEASUREMENT   # Enable statistics

    def __init__(self, coordinator: KwiksetDeviceDataUpdateCoordinator) -> None:
        """Initialize the battery sensor.

        Args:
            coordinator: Device coordinator for this lock
        """
        # Bronze tier: entity_unique_id via parent class
        # Creates unique_id: {device_id}_battery
        super().__init__("battery", coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the current battery percentage.

        Reads from coordinator (never API directly).
        Returns None if battery data is unavailable.

        Returns:
            Battery percentage (0-100) or None if unknown
        """
        return self.coordinator.battery_percentage