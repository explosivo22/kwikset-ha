"""Base entity class for Kwikset entities.

This module provides the base entity class that all Kwikset entities inherit from.
It follows the Home Assistant Platinum Quality Scale entity architecture patterns:

Architecture:
    - Uses CoordinatorEntity for automatic state updates from the coordinator
    - Implements has_entity_name=True for proper entity naming (HA auto-prefixes device name)
    - Uses translation_key for localized entity names via strings.json
    - Provides consistent device_info for device registry grouping
    - Delegates availability to coordinator's last_update_success

Quality Scale Compliance:
    Bronze tier:
        - has_entity_name: _attr_has_entity_name = True
        - entity_unique_id: Format {device_id}_{entity_type}

    Silver tier:
        - entity_unavailable: available property checks last_update_success
        - log_when_unavailable: Coordinator handles logging, entity reflects state

    Platinum tier:
        - strict_typing: Full type annotations with TYPE_CHECKING imports
        - Uses _attr_ pattern for cached properties (HA best practice)

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

Coordinator Pattern:
    All entities use the coordinator for:
    - State data (via coordinator properties like status, battery_percentage)
    - Actions (via coordinator methods like lock(), unlock(), set_led())
    - Availability (via coordinator.last_update_success)
    
    Entities should NEVER call the API directly.
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

    Provides common functionality for all Kwikset entity platforms:
        - Automatic state updates via DataUpdateCoordinator
        - Consistent device_info for device registry grouping
        - Standardized unique_id format: {device_id}_{entity_type}
        - Availability based on coordinator update success
        - Translation key support for localized entity names

    Quality Scale Implementation:
        Bronze - has_entity_name:
            _attr_has_entity_name = True enables HA's entity naming.
            Combined with translation_key, creates proper entity names.
        
        Bronze - entity_unique_id:
            Unique ID format: {device_id}_{entity_type}
            Ensures entities are uniquely identifiable across restarts.
        
        Silver - entity_unavailable:
            Uses _attr_available pattern for cached_property compatibility.
            Entities show unavailable when coordinator fails to update.

    Subclasses must:
        - Set `_attr_translation_key` class attribute for entity naming
        - Call `super().__init__(entity_type, coordinator)`
        - Implement platform-specific properties (is_locked, native_value, etc.)
        - Use coordinator properties for state data (never call API directly)

    Example:
        class KwiksetLock(KwiksetEntity, LockEntity):
            _attr_translation_key = "lock"
            _attr_name = None  # Use device name for primary entity

            def __init__(self, coordinator):
                super().__init__("lock", coordinator)
    """

    # Bronze tier: has_entity_name
    # Enable HA entity name concatenation (device name + entity name)
    _attr_has_entity_name = True

    def __init__(
        self,
        entity_type: str,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
    ) -> None:
        """Initialize the Kwikset entity.

        Bronze tier: entity_unique_id
        Creates a unique_id in the format {device_id}_{entity_type}.
        This ensures entities are uniquely identifiable and survive restarts.

        Args:
            entity_type: Identifier for the entity type (e.g., "lock", "battery").
                Used to construct unique_id as {device_id}_{entity_type}.
            coordinator: The device coordinator managing data updates.
        """
        super().__init__(coordinator)
        # Bronze tier: entity_unique_id - format: {device_id}_{entity_type}
        self._attr_unique_id = f"{coordinator.device_id}_{entity_type}"
        # Set device_info via _attr_ pattern for cached_property compatibility
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=coordinator.device_name,
            sw_version=coordinator.firmware_version,
        )