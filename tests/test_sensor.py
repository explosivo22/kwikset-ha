"""Tests for Kwikset sensor entity."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from custom_components.kwikset.sensor import KwiksetBatterySensor

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_NAME


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.device_id = MOCK_DEVICE_ID
    coordinator.device_name = MOCK_DEVICE_NAME
    coordinator.manufacturer = "Kwikset"
    coordinator.model = "Halo Touch"
    coordinator.firmware_version = "1.2.3"
    coordinator.battery_percentage = 85
    coordinator.last_update_success = True
    return coordinator


async def test_battery_sensor_init(mock_coordinator: MagicMock) -> None:
    """Test battery sensor initialization."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor._attr_unique_id == f"{MOCK_DEVICE_ID}_battery"
    assert sensor._attr_translation_key == "battery"


async def test_battery_sensor_device_class(mock_coordinator: MagicMock) -> None:
    """Test battery sensor device class."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor._attr_device_class == SensorDeviceClass.BATTERY


async def test_battery_sensor_unit(mock_coordinator: MagicMock) -> None:
    """Test battery sensor unit of measurement."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor._attr_native_unit_of_measurement == PERCENTAGE


async def test_battery_sensor_entity_category(mock_coordinator: MagicMock) -> None:
    """Test battery sensor entity category."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor._attr_entity_category == EntityCategory.DIAGNOSTIC


async def test_battery_sensor_state_class(mock_coordinator: MagicMock) -> None:
    """Test battery sensor state class."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT


async def test_battery_sensor_native_value(mock_coordinator: MagicMock) -> None:
    """Test battery sensor native value."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor.native_value == 85


async def test_battery_sensor_native_value_none(mock_coordinator: MagicMock) -> None:
    """Test battery sensor native value when None."""
    mock_coordinator.battery_percentage = None
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor.native_value is None


async def test_battery_sensor_device_info(mock_coordinator: MagicMock) -> None:
    """Test battery sensor device info."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    device_info = sensor.device_info
    
    assert ("kwikset", MOCK_DEVICE_ID) in device_info["identifiers"]
    assert device_info["manufacturer"] == "Kwikset"


async def test_battery_sensor_available(mock_coordinator: MagicMock) -> None:
    """Test battery sensor availability."""
    sensor = KwiksetBatterySensor(mock_coordinator)
    
    assert sensor.available is True
    
    mock_coordinator.last_update_success = False
    assert sensor.available is False
