"""Tests for Kwikset entity base class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.kwikset.entity import KwiksetEntity

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
    coordinator.serial_number = "SN12345678"
    coordinator.last_update_success = True
    return coordinator


class TestKwiksetEntity:
    """Tests for the KwiksetEntity base class."""

    async def test_entity_init_unique_id(self, mock_coordinator: MagicMock) -> None:
        """Test entity unique_id is correctly formatted."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        assert entity._attr_unique_id == f"{MOCK_DEVICE_ID}_test_type"

    async def test_entity_has_entity_name(self, mock_coordinator: MagicMock) -> None:
        """Test has_entity_name is True."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        assert entity._attr_has_entity_name is True

    async def test_entity_device_info_identifiers(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test device_info contains correct identifiers."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        device_info = entity._attr_device_info

        assert ("kwikset", MOCK_DEVICE_ID) in device_info["identifiers"]

    async def test_entity_device_info_manufacturer(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test device_info contains manufacturer."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        device_info = entity._attr_device_info

        assert device_info["manufacturer"] == "Kwikset"

    async def test_entity_device_info_model(self, mock_coordinator: MagicMock) -> None:
        """Test device_info contains model."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        device_info = entity._attr_device_info

        assert device_info["model"] == "Halo Touch"

    async def test_entity_device_info_name(self, mock_coordinator: MagicMock) -> None:
        """Test device_info contains device name."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        device_info = entity._attr_device_info

        assert device_info["name"] == MOCK_DEVICE_NAME

    async def test_entity_device_info_sw_version(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test device_info contains firmware version."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        device_info = entity._attr_device_info

        assert device_info["sw_version"] == "1.2.3"

    async def test_entity_stores_coordinator_reference(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test entity stores coordinator reference."""
        entity = KwiksetEntity("test_type", mock_coordinator)

        assert entity.coordinator is mock_coordinator

    async def test_entity_unique_id_with_different_types(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test unique_id varies by entity_type."""
        entity_lock = KwiksetEntity("lock", mock_coordinator)
        entity_battery = KwiksetEntity("battery", mock_coordinator)
        entity_led = KwiksetEntity("led_switch", mock_coordinator)

        assert entity_lock._attr_unique_id == f"{MOCK_DEVICE_ID}_lock"
        assert entity_battery._attr_unique_id == f"{MOCK_DEVICE_ID}_battery"
        assert entity_led._attr_unique_id == f"{MOCK_DEVICE_ID}_led_switch"

    async def test_entity_unique_ids_are_unique(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test that different entity types produce different unique_ids."""
        entity1 = KwiksetEntity("type1", mock_coordinator)
        entity2 = KwiksetEntity("type2", mock_coordinator)

        assert entity1._attr_unique_id != entity2._attr_unique_id
