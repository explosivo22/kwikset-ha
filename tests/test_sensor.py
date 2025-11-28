"""Tests for Kwikset sensor entity.

This module tests the sensor entities using the EntityDescription pattern.
Tests cover:
    - Sensor description tuple immutability and content
    - KwiksetSensor initialization with descriptions
    - Proper value extraction via value_fn
    - Entity category, device class, and state class
    - Device info and availability inheritance
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from custom_components.kwikset.sensor import SENSOR_DESCRIPTIONS
from custom_components.kwikset.sensor import KwiksetSensor
from custom_components.kwikset.sensor import KwiksetSensorEntityDescription

from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_DEVICE_NAME


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


@pytest.fixture
def battery_description() -> KwiksetSensorEntityDescription:
    """Get the battery sensor description from SENSOR_DESCRIPTIONS."""
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key == "battery":
            return desc
    raise ValueError("Battery description not found in SENSOR_DESCRIPTIONS")


class TestSensorDescriptions:
    """Test the SENSOR_DESCRIPTIONS tuple."""

    def test_sensor_descriptions_is_tuple(self) -> None:
        """Test that SENSOR_DESCRIPTIONS is a tuple (immutable)."""
        assert isinstance(SENSOR_DESCRIPTIONS, tuple)

    def test_sensor_descriptions_not_empty(self) -> None:
        """Test that SENSOR_DESCRIPTIONS contains at least one description."""
        assert len(SENSOR_DESCRIPTIONS) > 0

    def test_battery_description_exists(self) -> None:
        """Test that battery sensor description exists."""
        keys = [desc.key for desc in SENSOR_DESCRIPTIONS]
        assert "battery" in keys

    def test_all_descriptions_are_valid_type(self) -> None:
        """Test that all descriptions are KwiksetSensorEntityDescription."""
        for desc in SENSOR_DESCRIPTIONS:
            assert isinstance(desc, KwiksetSensorEntityDescription)

    def test_all_descriptions_have_value_fn(self) -> None:
        """Test that all descriptions have a value_fn callable."""
        for desc in SENSOR_DESCRIPTIONS:
            assert callable(desc.value_fn)


class TestBatteryDescription:
    """Test the battery sensor description properties."""

    def test_battery_translation_key(
        self, battery_description: KwiksetSensorEntityDescription
    ) -> None:
        """Test battery sensor translation key."""
        assert battery_description.translation_key == "battery"

    def test_battery_device_class(
        self, battery_description: KwiksetSensorEntityDescription
    ) -> None:
        """Test battery sensor device class."""
        assert battery_description.device_class == SensorDeviceClass.BATTERY

    def test_battery_unit(
        self, battery_description: KwiksetSensorEntityDescription
    ) -> None:
        """Test battery sensor unit of measurement."""
        assert battery_description.native_unit_of_measurement == PERCENTAGE

    def test_battery_entity_category(
        self, battery_description: KwiksetSensorEntityDescription
    ) -> None:
        """Test battery sensor entity category."""
        assert battery_description.entity_category == EntityCategory.DIAGNOSTIC

    def test_battery_state_class(
        self, battery_description: KwiksetSensorEntityDescription
    ) -> None:
        """Test battery sensor state class."""
        assert battery_description.state_class == SensorStateClass.MEASUREMENT


class TestKwiksetSensor:
    """Test the KwiksetSensor entity class."""

    async def test_sensor_init(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test sensor initialization with description."""
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        assert sensor._attr_unique_id == f"{MOCK_DEVICE_ID}_battery"
        assert sensor.entity_description == battery_description

    async def test_sensor_native_value(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test sensor native value via value_fn."""
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        assert sensor.native_value == 85

    async def test_sensor_native_value_none(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test sensor native value when None."""
        mock_coordinator.battery_percentage = None
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        assert sensor.native_value is None

    async def test_sensor_device_info(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test sensor device info inheritance from base class."""
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        device_info = sensor.device_info

        assert ("kwikset", MOCK_DEVICE_ID) in device_info["identifiers"]
        assert device_info["manufacturer"] == "Kwikset"

    async def test_sensor_available(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test sensor availability inheritance from base class."""
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        assert sensor.available is True

        mock_coordinator.last_update_success = False
        assert sensor.available is False

    async def test_sensor_has_entity_name(
        self,
        mock_coordinator: MagicMock,
        battery_description: KwiksetSensorEntityDescription,
    ) -> None:
        """Test that sensor has entity name flag set."""
        sensor = KwiksetSensor(mock_coordinator, battery_description)

        assert sensor._attr_has_entity_name is True
