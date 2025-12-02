"""Base entity class for Kwikset entities.

Provides the base entity class that all Kwikset entities inherit from,
implementing Home Assistant Platinum Quality Scale patterns.

Quality Scale:
    Bronze: has_entity_name, entity_unique_id
    Silver: entity_unavailable (via coordinator.last_update_success)
    Platinum: strict_typing, __slots__
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

    Provides:
        - Automatic state updates via DataUpdateCoordinator
        - Consistent device_info for device registry grouping
        - Unique ID format: {device_id}_{entity_type}
        - Availability based on coordinator.last_update_success

    Subclasses must set _attr_translation_key and call super().__init__().
    """

    # Platinum tier: __slots__ for memory efficiency
    __slots__ = ()

    # Bronze tier: has_entity_name - HA auto-prefixes device name
    _attr_has_entity_name = True

    def __init__(
        self,
        entity_type: str,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
    ) -> None:
        """Initialize the Kwikset entity.

        Args:
            entity_type: Entity type key (e.g., "lock", "battery") for unique_id.
            coordinator: Device coordinator for state and actions.
        """
        super().__init__(coordinator)

        # Bronze tier: entity_unique_id
        self._attr_unique_id = f"{coordinator.device_id}_{entity_type}"

        # Device registry info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=coordinator.device_name,
            sw_version=coordinator.firmware_version,
        )