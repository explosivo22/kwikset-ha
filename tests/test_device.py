"""Tests for Kwikset device coordinator."""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.kwikset.const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    MAX_RETRY_ATTEMPTS,
    TOKEN_REFRESH_BUFFER_SECONDS,
)
from custom_components.kwikset.device import (
    KwiksetDeviceData,
    KwiksetDeviceDataUpdateCoordinator,
)

from .conftest import MOCK_DEVICE_ID, MOCK_DEVICE_INFO, MOCK_DEVICE_NAME, MOCK_USER_INFO


def create_jwt_token(exp_seconds_from_now: int) -> str:
    """Create a mock JWT token with specified expiration."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').decode().rstrip("=")
    exp = int(time.time()) + exp_seconds_from_now
    payload_data = {"exp": exp, "sub": "test-user"}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(b"signature").decode().rstrip("=")
    return f"{header}.{payload}.{signature}"


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client."""
    api = MagicMock()
    api.device = MagicMock()
    api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
    api.device.lock_device = AsyncMock()
    api.device.unlock_device = AsyncMock()
    api.device.set_ledstatus = AsyncMock()
    api.device.set_audiostatus = AsyncMock()
    api.device.set_securescreenstatus = AsyncMock()
    api.user = MagicMock()
    api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
    api.async_renew_access_token = AsyncMock()
    api.access_token = "new_access_token"
    api.refresh_token = "new_refresh_token"
    return api


@pytest.fixture
def mock_config_entry_with_token() -> MagicMock:
    """Create a mock config entry with a valid token."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    # Create token that expires in 1 hour
    valid_token = create_jwt_token(3600)
    entry.data = {
        CONF_ACCESS_TOKEN: valid_token,
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    return entry


@pytest.fixture
def mock_config_entry_expiring_soon() -> MagicMock:
    """Create a mock config entry with a token expiring soon."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    # Create token that expires in 2 minutes (less than 5 min buffer)
    expiring_token = create_jwt_token(120)
    entry.data = {
        CONF_ACCESS_TOKEN: expiring_token,
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    return entry


async def test_coordinator_init(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test coordinator initialization."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    assert coordinator.device_id == MOCK_DEVICE_ID
    assert coordinator.device_name == MOCK_DEVICE_NAME
    assert coordinator.manufacturer == "Kwikset"
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator._token_expiry is not None


async def test_coordinator_token_expiry_parsing(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test JWT token expiry is parsed correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    assert coordinator._token_expiry is not None
    # Token should expire roughly 1 hour from now
    now = datetime.now(timezone.utc)
    assert coordinator._token_expiry > now
    assert coordinator._token_expiry < now + timedelta(hours=2)


async def test_coordinator_token_not_expiring_soon(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test token check returns False when token is valid."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    assert coordinator._is_token_expiring_soon() is False


async def test_coordinator_token_expiring_soon(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_expiring_soon: MagicMock
) -> None:
    """Test token check returns True when token is expiring soon."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_expiring_soon
    )
    
    assert coordinator._is_token_expiring_soon() is True


async def test_ensure_valid_token_refreshes_when_expiring(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_expiring_soon: MagicMock
) -> None:
    """Test _ensure_valid_token refreshes token when expiring soon."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_expiring_soon
    )
    
    await coordinator._ensure_valid_token()
    
    mock_api_client.async_renew_access_token.assert_called_once()
    hass.config_entries.async_update_entry.assert_called_once()


async def test_ensure_valid_token_skips_when_valid(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test _ensure_valid_token does nothing when token is valid."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    await coordinator._ensure_valid_token()
    
    mock_api_client.async_renew_access_token.assert_not_called()


async def test_ensure_valid_token_auth_error(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_expiring_soon: MagicMock
) -> None:
    """Test _ensure_valid_token raises ConfigEntryAuthFailed on auth error."""
    from aiokwikset.api import Unauthenticated
    
    mock_api_client.async_renew_access_token.side_effect = Unauthenticated("Token expired")
    
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_expiring_soon
    )
    
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._ensure_valid_token()


async def test_api_call_with_retry_success(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test API call succeeds on first attempt."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    result = await coordinator._async_api_call_with_retry(
        mock_api_client.device.get_device_info,
        MOCK_DEVICE_ID,
    )
    
    assert result == MOCK_DEVICE_INFO
    mock_api_client.device.get_device_info.assert_called_once_with(MOCK_DEVICE_ID)


async def test_api_call_with_retry_retries_on_transient_error(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test API call retries on transient errors."""
    from aiokwikset.errors import RequestError
    
    # Fail twice, then succeed
    mock_api_client.device.get_device_info.side_effect = [
        RequestError("Transient error 1"),
        RequestError("Transient error 2"),
        MOCK_DEVICE_INFO,
    ]
    
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    with patch("custom_components.kwikset.device.asyncio.sleep", new_callable=AsyncMock):
        result = await coordinator._async_api_call_with_retry(
            mock_api_client.device.get_device_info,
            MOCK_DEVICE_ID,
        )
    
    assert result == MOCK_DEVICE_INFO
    assert mock_api_client.device.get_device_info.call_count == 3


async def test_api_call_with_retry_fails_after_max_attempts(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test API call fails after max retry attempts."""
    from aiokwikset.errors import RequestError
    
    mock_api_client.device.get_device_info.side_effect = RequestError("Persistent error")
    
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    with patch("custom_components.kwikset.device.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_api_call_with_retry(
                mock_api_client.device.get_device_info,
                MOCK_DEVICE_ID,
            )
    
    assert f"after {MAX_RETRY_ATTEMPTS} attempts" in str(exc_info.value)
    assert mock_api_client.device.get_device_info.call_count == MAX_RETRY_ATTEMPTS


async def test_api_call_with_retry_no_retry_on_auth_error(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test API call does not retry on authentication errors."""
    from aiokwikset.api import Unauthenticated
    
    mock_api_client.device.get_device_info.side_effect = Unauthenticated("Auth failed")
    
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_api_call_with_retry(
            mock_api_client.device.get_device_info,
            MOCK_DEVICE_ID,
        )
    
    # Should only be called once - no retries for auth errors
    mock_api_client.device.get_device_info.assert_called_once()


async def test_coordinator_async_setup(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test coordinator setup fetches initial data."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    await coordinator._async_setup()
    
    mock_api_client.device.get_device_info.assert_called_with(MOCK_DEVICE_ID)
    assert coordinator._device_info == MOCK_DEVICE_INFO


async def test_coordinator_update_data(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test coordinator update fetches and parses data."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    
    data = await coordinator._async_update_data()
    
    assert data["door_status"] == "Locked"
    assert data["battery_percentage"] == 85
    assert data["model_number"] == "Halo Touch"
    assert data["serial_number"] == "SN12345678"
    assert data["firmware_version"] == "1.2.3"
    assert data["led_status"] is True
    assert data["audio_status"] is True
    assert data["secure_screen_status"] is False


class TestParseBool:
    """Tests for _parse_bool static method."""

    def test_parse_bool_none(self) -> None:
        """Test parsing None returns None."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(None) is None

    def test_parse_bool_true_bool(self) -> None:
        """Test parsing True returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(True) is True

    def test_parse_bool_false_bool(self) -> None:
        """Test parsing False returns False."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(False) is False

    def test_parse_bool_string_true(self) -> None:
        """Test parsing 'true' string returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("true") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("True") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("TRUE") is True

    def test_parse_bool_string_false(self) -> None:
        """Test parsing 'false' string returns False."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("false") is False
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("False") is False

    def test_parse_bool_string_one(self) -> None:
        """Test parsing '1' string returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("1") is True

    def test_parse_bool_string_zero(self) -> None:
        """Test parsing '0' string returns False."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("0") is False

    def test_parse_bool_string_yes(self) -> None:
        """Test parsing 'yes' string returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("yes") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("Yes") is True

    def test_parse_bool_string_on(self) -> None:
        """Test parsing 'on' string returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("on") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("On") is True

    def test_parse_bool_int_one(self) -> None:
        """Test parsing integer 1 returns True."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(1) is True

    def test_parse_bool_int_zero(self) -> None:
        """Test parsing integer 0 returns False."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(0) is False


async def test_coordinator_lock(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test lock action calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.lock()
    
    mock_api_client.user.get_info.assert_called()
    mock_api_client.device.lock_device.assert_called_with(
        MOCK_DEVICE_INFO, MOCK_USER_INFO
    )
    coordinator.async_request_refresh.assert_called_once()


async def test_coordinator_unlock(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test unlock action calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.unlock()
    
    mock_api_client.user.get_info.assert_called()
    mock_api_client.device.unlock_device.assert_called_with(
        MOCK_DEVICE_INFO, MOCK_USER_INFO
    )
    coordinator.async_request_refresh.assert_called_once()


async def test_coordinator_set_led_on(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test setting LED on calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.set_led(True)
    
    mock_api_client.device.set_ledstatus.assert_called_with(
        MOCK_DEVICE_INFO, "true"
    )
    coordinator.async_request_refresh.assert_called_once()


async def test_coordinator_set_led_off(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test setting LED off calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.set_led(False)
    
    mock_api_client.device.set_ledstatus.assert_called_with(
        MOCK_DEVICE_INFO, "false"
    )


async def test_coordinator_set_audio(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test setting audio calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.set_audio(True)
    
    mock_api_client.device.set_audiostatus.assert_called_with(
        MOCK_DEVICE_INFO, "true"
    )


async def test_coordinator_set_secure_screen(
    hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
) -> None:
    """Test setting secure screen calls API correctly."""
    coordinator = KwiksetDeviceDataUpdateCoordinator(
        hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
    )
    coordinator._device_info = MOCK_DEVICE_INFO
    coordinator.async_request_refresh = AsyncMock()
    
    await coordinator.set_secure_screen(True)
    
    mock_api_client.device.set_securescreenstatus.assert_called_with(
        MOCK_DEVICE_INFO, "true"
    )


class TestCoordinatorProperties:
    """Tests for coordinator properties."""

    @pytest.fixture
    def coordinator_with_data(
        self, hass: HomeAssistant, mock_api_client: MagicMock, mock_config_entry_with_token: MagicMock
    ) -> KwiksetDeviceDataUpdateCoordinator:
        """Create a coordinator with data set."""
        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass, mock_api_client, MOCK_DEVICE_ID, MOCK_DEVICE_NAME, 30, mock_config_entry_with_token
        )
        coordinator._device_info = MOCK_DEVICE_INFO
        coordinator.data = KwiksetDeviceData(
            device_info=MOCK_DEVICE_INFO,
            door_status="Locked",
            battery_percentage=85,
            model_number="Halo Touch",
            serial_number="SN12345678",
            firmware_version="1.2.3",
            led_status=True,
            audio_status=True,
            secure_screen_status=False,
        )
        return coordinator

    def test_id_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test id property returns device_id."""
        assert coordinator_with_data.id == MOCK_DEVICE_ID

    def test_device_name_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test device_name property."""
        assert coordinator_with_data.device_name == MOCK_DEVICE_NAME

    def test_manufacturer_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test manufacturer property."""
        assert coordinator_with_data.manufacturer == "Kwikset"

    def test_model_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test model property from data."""
        assert coordinator_with_data.model == "Halo Touch"

    def test_battery_percentage_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test battery_percentage property."""
        assert coordinator_with_data.battery_percentage == 85

    def test_firmware_version_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test firmware_version property."""
        assert coordinator_with_data.firmware_version == "1.2.3"

    def test_serial_number_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test serial_number property."""
        assert coordinator_with_data.serial_number == "SN12345678"

    def test_status_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test status property."""
        assert coordinator_with_data.status == "Locked"

    def test_led_status_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test led_status property."""
        assert coordinator_with_data.led_status is True

    def test_audio_status_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test audio_status property."""
        assert coordinator_with_data.audio_status is True

    def test_secure_screen_status_property(
        self, coordinator_with_data: KwiksetDeviceDataUpdateCoordinator
    ) -> None:
        """Test secure_screen_status property."""
        assert coordinator_with_data.secure_screen_status is False
