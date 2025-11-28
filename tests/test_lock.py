"""Tests for Kwikset lock entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.kwikset.lock import KwiksetLock

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
    coordinator.status = "Locked"
    coordinator.last_update_success = True
    coordinator.lock = AsyncMock()
    coordinator.unlock = AsyncMock()
    return coordinator


async def test_lock_entity_init(mock_coordinator: MagicMock) -> None:
    """Test lock entity initialization."""
    lock = KwiksetLock(mock_coordinator)
    
    assert lock._attr_unique_id == f"{MOCK_DEVICE_ID}_lock"
    assert lock._attr_translation_key == "lock"
    assert lock._attr_name is None  # Primary entity uses device name


async def test_lock_is_locked_true(mock_coordinator: MagicMock) -> None:
    """Test is_locked returns True when locked."""
    mock_coordinator.status = "Locked"
    lock = KwiksetLock(mock_coordinator)
    
    assert lock._attr_is_locked is True


async def test_lock_is_locked_false(mock_coordinator: MagicMock) -> None:
    """Test is_locked returns False when unlocked."""
    mock_coordinator.status = "Unlocked"
    lock = KwiksetLock(mock_coordinator)
    
    assert lock._attr_is_locked is False


async def test_lock_is_locked_unknown(mock_coordinator: MagicMock) -> None:
    """Test is_locked returns None when unknown."""
    mock_coordinator.status = "Unknown"
    lock = KwiksetLock(mock_coordinator)
    
    assert lock._attr_is_locked is None


async def test_lock_async_lock(mock_coordinator: MagicMock) -> None:
    """Test async_lock calls coordinator."""
    lock = KwiksetLock(mock_coordinator)
    
    await lock.async_lock()
    
    mock_coordinator.lock.assert_called_once()


async def test_lock_async_lock_failure(mock_coordinator: MagicMock) -> None:
    """Test async_lock raises HomeAssistantError on failure."""
    mock_coordinator.lock = AsyncMock(side_effect=Exception("API error"))
    lock = KwiksetLock(mock_coordinator)
    
    with pytest.raises(HomeAssistantError):
        await lock.async_lock()


async def test_lock_async_unlock(mock_coordinator: MagicMock) -> None:
    """Test async_unlock calls coordinator."""
    lock = KwiksetLock(mock_coordinator)
    
    await lock.async_unlock()
    
    mock_coordinator.unlock.assert_called_once()


async def test_lock_async_unlock_failure(mock_coordinator: MagicMock) -> None:
    """Test async_unlock raises HomeAssistantError on failure."""
    mock_coordinator.unlock = AsyncMock(side_effect=Exception("API error"))
    lock = KwiksetLock(mock_coordinator)
    
    with pytest.raises(HomeAssistantError):
        await lock.async_unlock()


async def test_lock_device_info(mock_coordinator: MagicMock) -> None:
    """Test device_info returns correct data."""
    lock = KwiksetLock(mock_coordinator)
    
    device_info = lock._attr_device_info
    
    assert ("kwikset", MOCK_DEVICE_ID) in device_info["identifiers"]
    assert device_info["manufacturer"] == "Kwikset"
    assert device_info["model"] == "Halo Touch"
    assert device_info["name"] == MOCK_DEVICE_NAME


async def test_lock_coordinator_update(mock_coordinator: MagicMock) -> None:
    """Test that coordinator update refreshes lock state."""
    mock_coordinator.status = "Locked"
    lock = KwiksetLock(mock_coordinator)
    assert lock._attr_is_locked is True
    
    # Simulate status change and coordinator update
    mock_coordinator.status = "Unlocked"
    lock._handle_coordinator_update()
    
    assert lock._attr_is_locked is False
