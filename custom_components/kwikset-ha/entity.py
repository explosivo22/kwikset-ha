"""Base entity class for Kwikset entities.

This module provides the base entity class that all Kwikset entities inherit from.
It follows the Home Assistant Platinum Quality Scale entity architecture patterns:

Architecture:
    - Uses CoordinatorEntity for automatic state updates from the coordinator
    - Implements has_entity_name=True for proper entity naming (HA auto-prefixes device name)
    - Uses translation_key for localized entity names via strings.json
    - Provides consistent device_info for device registry grouping
    - Delegates availability to coordinator's last_update_success

Entity Naming:
    All entities use `_attr_translation_key` instead of `_attr_name`. This maps to
    entries in strings.json under the "entity" section:
    
        entity.<platform>.<translation_key>.name
    
    Example: _attr_translation_key = "lock" → entity.lock.lock.name → "Lock"
    
    With _attr_has_entity_name = True, Home Assistant automatically creates
    the full entity name as "<Device Name> <Entity Name>".

Unique ID Format:
    {device_id}_{entity_type}
    Example: "abc123_lock", "abc123_battery", "abc123_led_switch"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .device import KwiksetDeviceDataUpdateCoordinator


class KwiksetEntity(CoordinatorEntity["KwiksetDeviceDataUpdateCoordinator"]):
    """Base class for all Kwikset entities.

    Provides common functionality:
        - Automatic state updates via DataUpdateCoordinator
        - Consistent device_info for device registry grouping
        - Standardized unique_id format: {device_id}_{entity_type}
        - Availability based on coordinator update success
        - Translation key support for localized entity names

    Subclasses must:
        - Set `_attr_translation_key` class attribute for entity naming
        - Call `super().__init__(entity_type, coordinator)`
        - Implement platform-specific properties (is_locked, native_value, etc.)
        - Use coordinator properties for state data (never call API directly)

    Example:
        class KwiksetLock(KwiksetEntity, LockEntity):
            _attr_translation_key = "lock"

            def __init__(self, coordinator):
                super().__init__("lock", coordinator)
    """

    # Enable HA entity name concatenation (device name + entity name)
    _attr_has_entity_name = True

    def __init__(
        self,
        entity_type: str,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
    ) -> None:
        """Initialize the Kwikset entity.

        Args:
            entity_type: Identifier for the entity type (e.g., "lock", "battery").
                Used to construct unique_id as {device_id}_{entity_type}.
            coordinator: The device coordinator managing data updates.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{entity_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry.

        All entities from the same device share this device_info,
        which groups them together in the HA device registry.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=self.coordinator.manufacturer,
            model=self.coordinator.model,
            name=self.coordinator.device_name,
            sw_version=self.coordinator.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Availability is determined by the coordinator's last update status.
        If the coordinator fails to fetch data, all entities become unavailable.
        """
        return self.coordinator.last_update_success