"""Fixtures for Kwikset Smart Locks tests.

Provides reusable mocks and fixtures for testing all aspects of the
Kwikset integration following Home Assistant testing best practices.

Architecture:
    - Mock API fixtures for unit tests
    - Config entry factories for integration tests
    - Coordinator mocks for entity tests
    - JWT token generation for authentication tests

Quality Scale: Platinum tier - comprehensive test infrastructure.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

# =============================================================================
# Pytest-asyncio Fixtures
# =============================================================================


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests.

    Required by pytest-homeassistant-custom-component.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests.

    This fixture is automatically applied to all tests, enabling
    the custom Kwikset integration to be loaded.
    """
    return


from custom_components.kwikset.const import CONF_ACCESS_TOKEN
from custom_components.kwikset.const import CONF_HOME_ID
from custom_components.kwikset.const import CONF_ID_TOKEN
from custom_components.kwikset.const import CONF_REFRESH_INTERVAL
from custom_components.kwikset.const import CONF_REFRESH_TOKEN
from custom_components.kwikset.const import DEFAULT_REFRESH_INTERVAL
from custom_components.kwikset.const import DOMAIN

# =============================================================================
# Mock Data Constants
# =============================================================================

MOCK_EMAIL = "user@example.com"
MOCK_PASSWORD = "secure_password123"
MOCK_HOME_ID = "home_001"
MOCK_HOME_NAME = "My House"

MOCK_DEVICE_ID = "device_123"
MOCK_DEVICE_NAME = "Front Door Lock"
MOCK_DEVICE_ID_2 = "device_456"
MOCK_DEVICE_NAME_2 = "Back Door Lock"

MOCK_DEVICES = [
    {
        "deviceid": MOCK_DEVICE_ID,
        "devicename": MOCK_DEVICE_NAME,
    },
    {
        "deviceid": MOCK_DEVICE_ID_2,
        "devicename": MOCK_DEVICE_NAME_2,
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

MOCK_DEVICE_INFO_2 = {
    "deviceid": MOCK_DEVICE_ID_2,
    "devicename": MOCK_DEVICE_NAME_2,
    "doorstatus": "Unlocked",
    "batterypercentage": 72,
    "modelnumber": "Halo WiFi",
    "serialnumber": "SN87654321",
    "firmwarebundleversion": "2.0.1",
    "ledstatus": "false",
    "audiostatus": False,
    "securescreenstatus": "true",
}

MOCK_USER_INFO = {
    "userid": "user_abc123",
    "email": MOCK_EMAIL,
    "firstname": "John",
    "lastname": "Doe",
}

MOCK_HOMES = [
    {
        "homeid": MOCK_HOME_ID,
        "homename": MOCK_HOME_NAME,
    },
    {
        "homeid": "home_002",
        "homename": "Vacation Home",
    },
]

MOCK_DEVICE_HISTORY = {
    "data": [
        {
            "id": 2640374935,
            "lse": "61",
            "user": "John Doe",
            "timestamp": 1770928208,
            "eventtype": "Mobile ( WiFi, LTE, ETC)",
            "event": "Locked",
            "eventcategory": "Lock Mechanism",
            "devicename": "Front Door",
            "homeid": "home_001",
            "timezone": "GMT-6:00",
            "isissue": 0,
        },
        {
            "id": 2640374934,
            "lse": "60",
            "user": "Jane Doe",
            "timestamp": 1770924608,
            "eventtype": "Keypad",
            "event": "Unlocked",
            "eventcategory": "Lock Mechanism",
            "devicename": "Front Door",
            "homeid": "home_001",
            "timezone": "GMT-6:00",
            "isissue": 0,
        },
    ],
    "total": 2,
    "issues": [],
}


def generate_mock_jwt(expiry_seconds: int = 3600) -> str:
    """Generate a mock JWT token with configurable expiry.

    Args:
        expiry_seconds: Seconds from now until token expires.

    Returns:
        Base64-encoded mock JWT token string.
    """
    header = (
        base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    )
    payload_data = {"exp": time.time() + expiry_seconds, "sub": "mock_user"}
    payload = (
        base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    )
    signature = base64.urlsafe_b64encode(b"mock_signature").decode().rstrip("=")
    return f"{header}.{payload}.{signature}"


def generate_expired_jwt() -> str:
    """Generate an expired JWT token for testing refresh logic."""
    return generate_mock_jwt(expiry_seconds=-100)


MOCK_ACCESS_TOKEN = generate_mock_jwt()
MOCK_ID_TOKEN = generate_mock_jwt()
MOCK_REFRESH_TOKEN = "mock_refresh_token_abc123"

MOCK_ENTRY_DATA = {
    CONF_EMAIL: MOCK_EMAIL,
    CONF_HOME_ID: MOCK_HOME_ID,
    CONF_ID_TOKEN: MOCK_ID_TOKEN,
    CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
}

MOCK_ENTRY_OPTIONS = {
    CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
}

# Access code mock result
MOCK_ACCESS_CODE_RESULT = MagicMock()
MOCK_ACCESS_CODE_RESULT.token = "mock_token_abc123"
MOCK_ACCESS_CODE_RESULT.last_update_status = 1770928208

# Home user mock data
MOCK_HOME_USERS: list[dict[str, Any]] = [
    {
        "sharedwithname": "Test User",
        "email": "test@example.com",
        "useraccesslevel": "Admin",
    },
    {
        "sharedwithname": "Guest User",
        "email": "guest@example.com",
        "useraccesslevel": "Member",
    },
]


# =============================================================================
# API Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Create a mock aiokwikset API client for __init__.py tests.

    Patches the API class in the main integration module.
    Also patches async_get_clientsession to prevent pycares thread creation.
    """
    with patch("custom_components.kwikset.API") as mock_api_class:
        with patch("custom_components.kwikset.async_get_clientsession") as mock_session:
            # Return a MagicMock for the session
            mock_session.return_value = MagicMock()

            api = MagicMock()

            # Token properties
            api.id_token = MOCK_ID_TOKEN
            api.access_token = MOCK_ACCESS_TOKEN
            api.refresh_token = MOCK_REFRESH_TOKEN
            api.is_authenticated = True

            # Async authentication methods
            api.async_login = AsyncMock()
            api.async_authenticate_with_tokens = AsyncMock()
            api.async_renew_access_token = AsyncMock()
            api.async_respond_to_mfa_challenge = AsyncMock()
            api.async_close = AsyncMock()

            # User namespace
            api.user = MagicMock()
            api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
            api.user.get_homes = AsyncMock(return_value=MOCK_HOMES)

            # Device namespace
            api.device = MagicMock()
            api.device.get_devices = AsyncMock(return_value=MOCK_DEVICES)
            api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
            api.device.lock_device = AsyncMock()
            api.device.unlock_device = AsyncMock()
            api.device.set_led_enabled = AsyncMock()
            api.device.set_audio_enabled = AsyncMock()
            api.device.set_secure_screen_enabled = AsyncMock()
            # Legacy methods for backwards compatibility
            api.device.set_ledstatus = AsyncMock()
            api.device.set_audiostatus = AsyncMock()
            api.device.set_securescreenstatus = AsyncMock()
            api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
            # Access code methods
            api.device.create_access_code = AsyncMock(
                return_value=MOCK_ACCESS_CODE_RESULT
            )
            api.device.edit_access_code = AsyncMock(
                return_value=MOCK_ACCESS_CODE_RESULT
            )
            api.device.disable_access_code = AsyncMock(
                return_value=MOCK_ACCESS_CODE_RESULT
            )
            api.device.enable_access_code = AsyncMock(
                return_value=MOCK_ACCESS_CODE_RESULT
            )
            api.device.delete_access_code = AsyncMock(return_value={"data": []})
            api.device.delete_all_access_codes = AsyncMock(return_value={"data": []})
            api.device.get_access_code_status = AsyncMock(
                return_value={"data": [{"status": "synced"}]}
            )

            # Subscriptions namespace (websocket events)
            api.subscriptions = MagicMock()
            api.subscriptions.set_callback = MagicMock()
            api.subscriptions.set_on_disconnect = MagicMock()
            api.subscriptions.set_on_reconnect = MagicMock()
            api.subscriptions.async_subscribe_device = AsyncMock()
            api.subscriptions.async_unsubscribe = AsyncMock()

            # Home user namespace
            api.home_user = MagicMock()
            api.home_user.get_users = AsyncMock(return_value=MOCK_HOME_USERS)
            api.home_user.invite_user = AsyncMock()
            api.home_user.update_user = AsyncMock()
            api.home_user.delete_user = AsyncMock()

            mock_api_class.return_value = api
            yield api


@pytest.fixture
def mock_api_config_flow() -> Generator[MagicMock, None, None]:
    """Create a mock aiokwikset API client for config_flow.py tests.

    Patches the API class and async_get_clientsession in the config_flow module.
    """
    with patch("custom_components.kwikset.config_flow.API") as mock_api_class:
        with patch(
            "custom_components.kwikset.config_flow.async_get_clientsession"
        ) as mock_session:
            mock_session.return_value = MagicMock()

            api = MagicMock()

            # Token properties
            api.id_token = MOCK_ID_TOKEN
            api.access_token = MOCK_ACCESS_TOKEN
            api.refresh_token = MOCK_REFRESH_TOKEN
            api.is_authenticated = True

            # Async authentication methods
            api.async_login = AsyncMock()
            api.async_authenticate_with_tokens = AsyncMock()
            api.async_renew_access_token = AsyncMock()
            api.async_respond_to_mfa_challenge = AsyncMock()
            api.async_request_custom_challenge_code = AsyncMock(
                return_value={"session": "updated_session", "challenge": "custom"}
            )
            api.async_close = AsyncMock()

            # User namespace
            api.user = MagicMock()
            api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
            api.user.get_homes = AsyncMock(return_value=MOCK_HOMES)

            # Device namespace
            api.device = MagicMock()
            api.device.get_devices = AsyncMock(return_value=MOCK_DEVICES)
            api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
            api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

            # Subscriptions namespace (websocket events)
            api.subscriptions = MagicMock()
            api.subscriptions.set_callback = MagicMock()
            api.subscriptions.set_on_disconnect = MagicMock()
            api.subscriptions.set_on_reconnect = MagicMock()
            api.subscriptions.async_subscribe_device = AsyncMock()
            api.subscriptions.async_unsubscribe = AsyncMock()

            mock_api_class.return_value = api
            yield api


@pytest.fixture
def mock_api_device() -> Generator[MagicMock, None, None]:
    """Create a mock aiokwikset API client for device.py coordinator tests.

    Patches the API at the device module level.
    """
    with patch("custom_components.kwikset.device.API") as mock_api_class:
        api = MagicMock()

        api.id_token = MOCK_ID_TOKEN
        api.access_token = MOCK_ACCESS_TOKEN
        api.refresh_token = MOCK_REFRESH_TOKEN
        api.is_authenticated = True

        api.async_authenticate_with_tokens = AsyncMock()
        api.async_renew_access_token = AsyncMock()
        api.async_close = AsyncMock()

        api.user = MagicMock()
        api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)

        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.lock_device = AsyncMock()
        api.device.unlock_device = AsyncMock()
        api.device.set_led_enabled = AsyncMock()
        api.device.set_audio_enabled = AsyncMock()
        api.device.set_secure_screen_enabled = AsyncMock()
        # Legacy methods for backwards compatibility
        api.device.set_ledstatus = AsyncMock()
        api.device.set_audiostatus = AsyncMock()
        api.device.set_securescreenstatus = AsyncMock()
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        # Access code methods
        api.device.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        api.device.edit_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        api.device.disable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        api.device.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        api.device.delete_access_code = AsyncMock(return_value={"data": []})
        api.device.delete_all_access_codes = AsyncMock(return_value={"data": []})
        api.device.get_access_code_status = AsyncMock(
            return_value={"data": [{"status": "synced"}]}
        )

        # Subscriptions namespace (websocket events)
        api.subscriptions = MagicMock()
        api.subscriptions.set_callback = MagicMock()
        api.subscriptions.set_on_disconnect = MagicMock()
        api.subscriptions.set_on_reconnect = MagicMock()
        api.subscriptions.async_subscribe_device = AsyncMock()
        api.subscriptions.async_unsubscribe = AsyncMock()

        mock_api_class.return_value = api
        yield api


# =============================================================================
# Coordinator Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator for entity testing.

    Returns a MagicMock that simulates KwiksetDeviceDataUpdateCoordinator.
    """
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
    coordinator.history_events = MOCK_DEVICE_HISTORY["data"]
    coordinator.last_event = "Locked"
    coordinator.last_event_user = "John Doe"
    coordinator.last_event_type = "Mobile ( WiFi, LTE, ETC)"
    coordinator.last_event_timestamp = 1770928208
    coordinator.last_event_category = "Lock Mechanism"
    coordinator.total_events = 2
    coordinator.last_update_success = True

    # Access code tracking properties
    coordinator.total_access_codes = 0
    coordinator.occupied_slots = []
    coordinator.access_codes = {}

    # Home user properties
    coordinator.home_user_count = 2
    coordinator.home_users = MOCK_HOME_USERS

    # Data dict for coordinator entity pattern
    coordinator.data = {
        "device_info": MOCK_DEVICE_INFO,
        "door_status": "Locked",
        "battery_percentage": 85,
        "model_number": "Halo Touch",
        "serial_number": "SN12345678",
        "firmware_version": "1.2.3",
        "led_status": True,
        "audio_status": True,
        "secure_screen_status": False,
        "history_events": MOCK_DEVICE_HISTORY["data"],
    }

    # Async action methods
    coordinator.lock = AsyncMock()
    coordinator.unlock = AsyncMock()
    coordinator.set_led = AsyncMock()
    coordinator.set_audio = AsyncMock()
    coordinator.set_secure_screen = AsyncMock()
    coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.disable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.delete_access_code = AsyncMock(return_value={"data": []})
    coordinator.delete_all_access_codes = AsyncMock(return_value={"data": []})
    coordinator.get_tracked_code = MagicMock(return_value=None)
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    return coordinator


@pytest.fixture
def mock_coordinator_unlocked() -> MagicMock:
    """Create a mock coordinator with unlocked state."""
    coordinator = MagicMock()
    coordinator.device_id = MOCK_DEVICE_ID
    coordinator.device_name = MOCK_DEVICE_NAME
    coordinator.manufacturer = "Kwikset"
    coordinator.model = "Halo Touch"
    coordinator.firmware_version = "1.2.3"
    coordinator.serial_number = "SN12345678"
    coordinator.battery_percentage = 85
    coordinator.status = "Unlocked"
    coordinator.led_status = True
    coordinator.audio_status = True
    coordinator.secure_screen_status = False
    coordinator.history_events = MOCK_DEVICE_HISTORY["data"]
    coordinator.last_event = "Locked"
    coordinator.last_event_user = "John Doe"
    coordinator.last_event_type = "Mobile ( WiFi, LTE, ETC)"
    coordinator.last_event_timestamp = 1770928208
    coordinator.last_event_category = "Lock Mechanism"
    coordinator.total_events = 2
    coordinator.last_update_success = True

    coordinator.data = {
        "device_info": MOCK_DEVICE_INFO,
        "door_status": "Unlocked",
        "battery_percentage": 85,
        "model_number": "Halo Touch",
        "serial_number": "SN12345678",
        "firmware_version": "1.2.3",
        "led_status": True,
        "audio_status": True,
        "secure_screen_status": False,
        "history_events": MOCK_DEVICE_HISTORY["data"],
    }

    coordinator.lock = AsyncMock()
    coordinator.unlock = AsyncMock()
    coordinator.set_led = AsyncMock()
    coordinator.set_audio = AsyncMock()
    coordinator.set_secure_screen = AsyncMock()
    coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.disable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
    coordinator.delete_access_code = AsyncMock(return_value={"data": []})
    coordinator.delete_all_access_codes = AsyncMock(return_value={"data": []})
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    return coordinator


# =============================================================================
# Config Entry Fixtures
# =============================================================================


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry for unit tests.

    Uses MockConfigEntry which properly integrates with Home Assistant's
    config entry system.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA.copy(),
        options=MOCK_ENTRY_OPTIONS.copy(),
        title=MOCK_HOME_NAME,
        unique_id=MOCK_HOME_ID,
        version=6,
    )
    entry.add_to_hass(hass)
    # Set state to SETUP_IN_PROGRESS for async_config_entry_first_refresh
    entry._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
    return entry


@pytest.fixture
def mock_config_entry_not_setup(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry that hasn't started setup.

    Useful for tests that don't need async_config_entry_first_refresh.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA.copy(),
        options=MOCK_ENTRY_OPTIONS.copy(),
        title=MOCK_HOME_NAME,
        unique_id=MOCK_HOME_ID,
        version=6,
    )
    entry.add_to_hass(hass)
    return entry


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def mock_device_info_response() -> dict[str, Any]:
    """Return mock device info response for API tests."""
    return MOCK_DEVICE_INFO.copy()


@pytest.fixture
def mock_devices_response() -> list[dict[str, Any]]:
    """Return mock devices list response for API tests."""
    return MOCK_DEVICES.copy()
