"""Support for Kwikset smart lock sensors.

This module provides sensor entities for Kwikset smart locks using the
EntityDescription pattern recommended by Home Assistant best practices.

Currently supports:
    - Battery percentage sensor (diagnostic category)

Architecture:
    - Uses frozen dataclass KwiksetSensorEntityDescription for sensor definitions
    - Sensors defined as a tuple (SENSOR_DESCRIPTIONS) for immutability
    - Uses translation_key for entity naming (Bronze: has_entity_name)
    - All state is retrieved via value_fn callback from coordinator
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

    Platinum tier:
        - strict_typing: Full type annotations including Callable types

Entity Categories:
    The battery sensor uses EntityCategory.DIAGNOSTIC because:
    - It provides status information about the device itself
    - It's not a primary control or measurement
    - Users typically don't want it on the main dashboard
    - HA automatically groups diagnostic entities together

Entity Description Pattern:
    This module follows Home Assistant's recommended EntityDescription pattern:
    - KwiksetSensorEntityDescription extends SensorEntityDescription
    - Uses frozen=True and kw_only=True for immutability and clarity
    - value_fn callable extracts state from coordinator
    - SENSOR_DESCRIPTIONS tuple holds all sensor definitions
    - Single KwiksetSensor class handles all sensor types
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
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

# Silver tier: parallel_updates
# Module-level declaration required by HA to limit concurrent API calls to 1
# While sensors are read-only, this ensures consistent behavior across platforms
PARALLEL_UPDATES: int = _PARALLEL_UPDATES


@dataclass(frozen=True, kw_only=True)
class KwiksetSensorEntityDescription(SensorEntityDescription):
    """Describes a Kwikset sensor entity.

    This dataclass extends Home Assistant's SensorEntityDescription to add
    a value_fn callback for extracting sensor values from the coordinator.

    Attributes:
        value_fn: Callable that takes a coordinator and returns the sensor value.
            Returns int | None for battery percentage.

    The frozen=True ensures immutability (required for hashability).

    Example:
        KwiksetSensorEntityDescription(
            key="battery",
            translation_key="battery",
            value_fn=lambda coord: coord.battery_percentage,
        )

    """

    value_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], int | None] = field()


# Sensor descriptions tuple - immutable collection of all sensor definitions
# Using tuple for immutability as recommended by HA best practices
SENSOR_DESCRIPTIONS: tuple[KwiksetSensorEntityDescription, ...] = (
    KwiksetSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.battery_percentage,
    ),
)


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

    Creates a KwiksetSensor for each description in SENSOR_DESCRIPTIONS
    for each device, enabling easy addition of new sensor types.

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
        Creates all sensor types for each new device using the
        SENSOR_DESCRIPTIONS tuple.
        """
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

        # Create a sensor entity for each description for each new device
        async_add_entities(
            KwiksetSensor(devices[device_id], description)
            for device_id in new_ids
            for description in SENSOR_DESCRIPTIONS
        )
        known_ids.update(new_ids)
        LOGGER.debug("Added sensor entities for devices: %s", new_ids)

    # Add existing devices
    _async_add_new_devices()

    # Listen for new device discovery events
    # Gold tier: dynamic_devices - runtime discovery support
    entry.async_on_unload(
        hass.bus.async_listen(
            f"{DOMAIN}_new_device", lambda _: _async_add_new_devices()
        )
    )


class KwiksetSensor(KwiksetEntity, SensorEntity):
    """Sensor entity for Kwikset smart locks.

    This class uses the EntityDescription pattern to handle multiple sensor types
    with a single implementation. The sensor's behavior is determined by the
    KwiksetSensorEntityDescription passed during initialization.

    Quality Scale Implementation:
        Bronze - has_entity_name:
            Uses entity_description.translation_key which maps to
            entity.sensor.<key>.name in strings.json

        Bronze - entity_unique_id:
            Inherited from KwiksetEntity: {device_id}_{description.key}

        Silver - entity_unavailable:
            Inherited from KwiksetEntity.available property

        Platinum - strict_typing:
            Full type annotations for entity_description and native_value

    Entity Description Pattern Benefits:
        - Single class handles all sensor types
        - Easy to add new sensors by adding to SENSOR_DESCRIPTIONS
        - Consistent behavior across all sensors
        - value_fn provides flexible state extraction
    """

    # Type hint for entity_description enables IDE autocompletion
    entity_description: KwiksetSensorEntityDescription

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        description: KwiksetSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity.

        Args:
            coordinator: Device coordinator for this lock
            description: Entity description defining sensor behavior

        """
        # Store entity description for access to value_fn and other properties
        self.entity_description = description
        # Bronze tier: entity_unique_id via parent class
        # Creates unique_id: {device_id}_{description.key}
        super().__init__(description.key, coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the current sensor value.

        Uses the value_fn from entity_description to extract the value
        from the coordinator. This pattern allows flexible value extraction
        without subclassing.

        Returns:
            Sensor value (type depends on sensor type) or None if unavailable

        """
        return self.entity_description.value_fn(self.coordinator)
