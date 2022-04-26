"""Support for Kwikset Smart lock sensors."""
from __future__ import annotations
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    PERCENTAGE
)

from .const import DOMAIN as KWIKSET_DOMAIN
from .device import KwiksetDeviceDataUpdateCoordinator
from .entity import KwiksetEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kwikset sensors from config entry."""
    devices: list[KwiksetDeviceDataUpdateCoordinator] = hass.data[KWIKSET_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.extend(
            [
                KwiksetBatterySensor(device),
            ]
        )
    async_add_entities(entities)

class KwiksetBatterySensor(KwiksetEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_unit_of_measurement = PERCENTAGE

    def __init__(self, device):
        """Initialize the battery sensor."""
        super().__init__("sensor", f"{device.device_name} Battery", device)
        self._state: float = None

    @property
    def state(self) ->int | None:
        """Return the current temperature."""
        if self._device.battery_percentage is None:
            return None
        return self._device.battery_percentage