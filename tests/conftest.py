"""Fixtures for Kwikset Smart Locks tests."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from custom_components.kwikset.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOME_ID,
    CONF_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

# Mock device data from API
MOCK_DEVICE_ID = "device_123"
MOCK_DEVICE_NAME = "Front Door Lock"

MOCK_DEVICES = [
    {
        "deviceid": MOCK_DEVICE_ID,
        "devicename": MOCK_DEVICE_NAME,
    },
    {
        "deviceid": "device_456",
        "devicename": "Back Door Lock",
    },
]

MOCK_DEVICE_INFO = {
    "deviceid": MOCK_DEVICE_ID,
    "devicename": MOCK_DEVICE_NAME,
    "doorstatus": "Locked",
    "batterypercentage": 85,
    "modelnumber": "Halo Touch",
    "serialnumber": "SN12345678",
    "firmwarebundleversion": "1.2.3",
    "ledstatus": "true",
    "audiostatus": True,
    "securescreenstatus": "false",
}

MOCK_USER_INFO = {
    "userid": "user_abc123",
    "email": "user@example.com",
    "firstname": "John",
    "lastname": "Doe",
}

MOCK_HOMES = [
    {
        "homeid": "home_001",
        "homename": "My House",
    },
    {
        "homeid": "home_002",
        "homename": "Vacation Home",
    },
]

MOCK_TOKENS = {
    "access_token": "mock_access_token_xyz",
    "refresh_token": "mock_refresh_token_abc",
}

MOCK_ENTRY_DATA = {
    CONF_EMAIL: "user@example.com",
    CONF_HOME_ID: "home_001",
    CONF_ACCESS_TOKEN: "old_access_token",
    CONF_REFRESH_TOKEN: "old_refresh_token",
}

MOCK_ENTRY_OPTIONS = {
    CONF_REFRESH_INTERVAL: 30,
}


@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Create a mock aiokwikset API client."""
    with patch("custom_components.kwikset.API") as mock_api_class:
        api = MagicMock()
        
        # Set token properties
        api.access_token = MOCK_TOKENS["access_token"]
        api.refresh_token = MOCK_TOKENS["refresh_token"]
        
        # Mock async methods
        api.async_login = AsyncMock()
        api.async_renew_access_token = AsyncMock()
        api.async_respond_to_mfa_challenge = AsyncMock()
        
        # Mock user namespace
        api.user = MagicMock()
        api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
        api.user.get_homes = AsyncMock(return_value=MOCK_HOMES)
        
        # Mock device namespace
        api.device = MagicMock()
        api.device.get_devices = AsyncMock(return_value=MOCK_DEVICES)
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.lock_device = AsyncMock()
        api.device.unlock_device = AsyncMock()
        api.device.set_ledstatus = AsyncMock()
        api.device.set_audiostatus = AsyncMock()
        api.device.set_securescreenstatus = AsyncMock()
        
        mock_api_class.return_value = api
        yield api


@pytest.fixture
def mock_api_config_flow() -> Generator[MagicMock, None, None]:
    """Create a mock aiokwikset API client for config flow tests."""
    with patch("custom_components.kwikset.config_flow.API") as mock_api_class:
        api = MagicMock()
        
        # Set token properties
        api.access_token = MOCK_TOKENS["access_token"]
        api.refresh_token = MOCK_TOKENS["refresh_token"]
        
        # Mock async methods
        api.async_login = AsyncMock()
        api.async_renew_access_token = AsyncMock()
        api.async_respond_to_mfa_challenge = AsyncMock()
        
        # Mock user namespace
        api.user = MagicMock()
        api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
        api.user.get_homes = AsyncMock(return_value=MOCK_HOMES)
        
        # Mock device namespace
        api.device = MagicMock()
        api.device.get_devices = AsyncMock(return_value=MOCK_DEVICES)
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        
        mock_api_class.return_value = api
        yield api


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator for entity testing."""
    coordinator = MagicMock()
    coordinator.device_id = MOCK_DEVICE_ID
    coordinator.device_name = MOCK_DEVICE_NAME
    coordinator.manufacturer = "Kwikset"
    coordinator.model = "Halo Touch"
    coordinator.firmware_version = "1.2.3"
    coordinator.serial_number = "SN12345678"
    coordinator.battery_percentage = 85
    coordinator.status = "Locked"
    coordinator.led_status = True
    coordinator.audio_status = True
    coordinator.secure_screen_status = False
    coordinator.last_update_success = True
    
    # Async methods
    coordinator.lock = AsyncMock()
    coordinator.unlock = AsyncMock()
    coordinator.set_led = AsyncMock()
    coordinator.set_audio = AsyncMock()
    coordinator.set_secure_screen = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    
    return coordinator


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.unique_id = "home_001"
    entry.domain = DOMAIN
    entry.title = "My House"
    entry.data = MOCK_ENTRY_DATA.copy()
    entry.options = MOCK_ENTRY_OPTIONS.copy()
    entry.version = 4
    entry.async_on_unload = MagicMock()
    return entry
