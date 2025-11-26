"""Tests for Kwikset switch entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.helpers.entity import EntityCategory

from custom_components.kwikset.switch import (
    SWITCH_DESCRIPTIONS,
    KwiksetSwitch,
)

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
    coordinator.led_status = True
    coordinator.audio_status = True
    coordinator.secure_screen_status = False
    coordinator.last_update_success = True
    coordinator.set_led = AsyncMock()
    coordinator.set_audio = AsyncMock()
    coordinator.set_secure_screen = AsyncMock()
    return coordinator


def get_description(key: str):
    """Get switch description by key."""
    return next(d for d in SWITCH_DESCRIPTIONS if d.key == key)


class TestKwiksetLEDSwitch:
    """Tests for LED switch entity."""

    async def test_led_switch_init(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch initialization."""
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch._attr_unique_id == f"{MOCK_DEVICE_ID}_led_switch"
        assert switch.entity_description.translation_key == "led_switch"

    async def test_led_switch_entity_category(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test LED switch entity category."""
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.entity_description.entity_category == EntityCategory.CONFIG

    async def test_led_switch_is_on_true(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch is_on when True."""
        mock_coordinator.led_status = True
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is True

    async def test_led_switch_is_on_false(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch is_on when False."""
        mock_coordinator.led_status = False
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is False

    async def test_led_switch_is_on_none(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch is_on when None."""
        mock_coordinator.led_status = None
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is None

    async def test_led_switch_turn_on(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch turn on."""
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_on()
        
        mock_coordinator.set_led.assert_called_once_with(True)

    async def test_led_switch_turn_off(self, mock_coordinator: MagicMock) -> None:
        """Test LED switch turn off."""
        desc = get_description("led_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_off()
        
        mock_coordinator.set_led.assert_called_once_with(False)


class TestKwiksetAudioSwitch:
    """Tests for Audio switch entity."""

    async def test_audio_switch_init(self, mock_coordinator: MagicMock) -> None:
        """Test Audio switch initialization."""
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch._attr_unique_id == f"{MOCK_DEVICE_ID}_audio_switch"
        assert switch.entity_description.translation_key == "audio_switch"

    async def test_audio_switch_entity_category(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Audio switch entity category."""
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.entity_description.entity_category == EntityCategory.CONFIG

    async def test_audio_switch_is_on_true(self, mock_coordinator: MagicMock) -> None:
        """Test Audio switch is_on when True."""
        mock_coordinator.audio_status = True
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is True

    async def test_audio_switch_is_on_false(self, mock_coordinator: MagicMock) -> None:
        """Test Audio switch is_on when False."""
        mock_coordinator.audio_status = False
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is False

    async def test_audio_switch_turn_on(self, mock_coordinator: MagicMock) -> None:
        """Test Audio switch turn on."""
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_on()
        
        mock_coordinator.set_audio.assert_called_once_with(True)

    async def test_audio_switch_turn_off(self, mock_coordinator: MagicMock) -> None:
        """Test Audio switch turn off."""
        desc = get_description("audio_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_off()
        
        mock_coordinator.set_audio.assert_called_once_with(False)


class TestKwiksetSecureScreenSwitch:
    """Tests for Secure Screen switch entity."""

    async def test_secure_screen_switch_init(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch initialization."""
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch._attr_unique_id == f"{MOCK_DEVICE_ID}_secure_screen_switch"
        assert switch.entity_description.translation_key == "secure_screen_switch"

    async def test_secure_screen_switch_entity_category(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch entity category."""
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.entity_description.entity_category == EntityCategory.CONFIG

    async def test_secure_screen_switch_is_on_true(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch is_on when True."""
        mock_coordinator.secure_screen_status = True
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is True

    async def test_secure_screen_switch_is_on_false(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch is_on when False."""
        mock_coordinator.secure_screen_status = False
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        assert switch.is_on is False

    async def test_secure_screen_switch_turn_on(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch turn on."""
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_on()
        
        mock_coordinator.set_secure_screen.assert_called_once_with(True)

    async def test_secure_screen_switch_turn_off(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test Secure Screen switch turn off."""
        desc = get_description("secure_screen_switch")
        switch = KwiksetSwitch(mock_coordinator, desc)
        
        await switch.async_turn_off()
        
        mock_coordinator.set_secure_screen.assert_called_once_with(False)


async def test_switch_device_info(mock_coordinator: MagicMock) -> None:
    """Test switch device info."""
    desc = get_description("led_switch")
    switch = KwiksetSwitch(mock_coordinator, desc)
    
    device_info = switch.device_info
    
    assert ("kwikset", MOCK_DEVICE_ID) in device_info["identifiers"]
    assert device_info["manufacturer"] == "Kwikset"


async def test_switch_available(mock_coordinator: MagicMock) -> None:
    """Test switch availability."""
    desc = get_description("led_switch")
    switch = KwiksetSwitch(mock_coordinator, desc)
    
    assert switch.available is True
    
    mock_coordinator.last_update_success = False
    assert switch.available is False
