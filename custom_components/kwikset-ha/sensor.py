"""Support for Kwikset Smart lock sensors."""
from __future__ import annotations
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory

from homeassistant.const import (
    PERCENTAGE
)

from .const import DOMAIN as KWIKSET_DOMAIN, LOGGER
from .device import KwiksetDeviceDataUpdateCoordinator
from .entity import KwiksetEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kwikset sensors from config entry."""
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = hass.data[KWIKSET_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    
    known_device_ids: set[str] = set()
    
    @callback
    def _add_new_devices() -> None:
        """Add new sensor entities for newly discovered devices."""
        entities = []
        current_device_ids = set(devices.keys())
        new_device_ids = current_device_ids - known_device_ids
        
        for device_id in new_device_ids:
            device = devices[device_id]
            entities.append(KwiksetBatterySensor(device))
            known_device_ids.add(device_id)
            LOGGER.debug("Added new sensor entity for device: %s", device_id)
        
        if entities:
            async_add_entities(entities)
    
    # Add existing devices
    _add_new_devices()
    
    # Listen for new devices - this callback will be triggered during reload
    # when new devices are discovered
    config_entry.async_on_unload(
        hass.bus.async_listen(
            f"{KWIKSET_DOMAIN}_new_device",
            lambda event: _add_new_devices()
        )
    )

class KwiksetBatterySensor(KwiksetEntity, SensorEntity):
    """Monitors the battery percentage."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("sensor", f"{device.device_name} Battery", device)

    @property
    def native_value(self) -> int | None:
        """Return the current battery percentage."""
        return self.coordinator.battery_percentage