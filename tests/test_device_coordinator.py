"""Tests for the KwiksetDeviceDataUpdateCoordinator.

Tests the device coordinator including:
- API call retry logic
- Device property access
- Lock/unlock and settings actions
- Error handling and recovery

Quality Scale: Platinum tier - coordinator is the central data management component.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from aiokwikset.errors import RequestError
from aiokwikset.errors import TokenExpiredError
from aiokwikset.errors import Unauthenticated
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import HomeAssistantError

from custom_components.kwikset.const import MAX_RETRY_ATTEMPTS
from custom_components.kwikset.device import KwiksetDeviceDataUpdateCoordinator

from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_DEVICE_INFO
from .conftest import MOCK_DEVICE_NAME
from .conftest import MOCK_USER_INFO

# =============================================================================
# Coordinator Initialization Tests
# =============================================================================


class TestCoordinatorInit:
    """Tests for coordinator initialization."""

    async def test_coordinator_initialization(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test coordinator initializes with correct values."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        assert coordinator.device_id == MOCK_DEVICE_ID
        assert coordinator.device_name == MOCK_DEVICE_NAME
        assert coordinator.update_interval == timedelta(seconds=30)

    async def test_coordinator_first_refresh(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test coordinator performs first refresh correctly."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85


# =============================================================================
# API Call Retry Logic Tests
# =============================================================================


class TestRetryLogic:
    """Tests for API call retry logic."""

    async def test_successful_api_call(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test successful API call returns data."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = await coordinator._api_call_with_retry(
            api.device.get_device_info,
            MOCK_DEVICE_ID,
        )

        assert result == MOCK_DEVICE_INFO

    async def test_retry_on_request_error(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test API call retries on RequestError."""
        api = MagicMock()
        api.device = MagicMock()

        # Fail twice, succeed on third attempt
        api.device.get_device_info = AsyncMock(
            side_effect=[
                RequestError("Network error"),
                RequestError("Network error"),
                MOCK_DEVICE_INFO,
            ]
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # Patch sleep to speed up test
        with patch(
            "custom_components.kwikset.device.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await coordinator._api_call_with_retry(
                api.device.get_device_info,
                MOCK_DEVICE_ID,
            )

        assert result == MOCK_DEVICE_INFO
        assert api.device.get_device_info.call_count == 3

    async def test_max_retries_exceeded_raises_home_assistant_error(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test HomeAssistantError with translation key is raised after max retries."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(
            side_effect=RequestError("Persistent network error")
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        with patch(
            "custom_components.kwikset.device.asyncio.sleep", new_callable=AsyncMock
        ):
            with pytest.raises(HomeAssistantError) as exc_info:
                await coordinator._api_call_with_retry(
                    api.device.get_device_info,
                    MOCK_DEVICE_ID,
                )

        # Verify exception uses translation key (Gold: exception-translations)
        assert exc_info.value.translation_key == "api_error"
        assert api.device.get_device_info.call_count == MAX_RETRY_ATTEMPTS

    async def test_auth_error_raises_config_entry_auth_failed(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test ConfigEntryAuthFailed is raised on authentication failure."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(
            side_effect=TokenExpiredError("Token expired")
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._api_call_with_retry(
                api.device.get_device_info,
                MOCK_DEVICE_ID,
            )

    async def test_unauthenticated_error_raises_config_entry_auth_failed(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test ConfigEntryAuthFailed is raised on Unauthenticated error."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(
            side_effect=Unauthenticated("Invalid credentials")
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._api_call_with_retry(
                api.device.get_device_info,
                MOCK_DEVICE_ID,
            )


# =============================================================================
# Device Property Tests
# =============================================================================


class TestDeviceProperties:
    """Tests for coordinator device properties."""

    async def test_device_properties_from_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test device properties are accessible after data load."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.manufacturer == "Kwikset"
        assert coordinator.model == "Halo Touch"
        assert coordinator.firmware_version == "1.2.3"
        assert coordinator.serial_number == "SN12345678"
        assert coordinator.battery_percentage == 85
        assert coordinator.status == "Locked"

    async def test_switch_properties(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test switch status properties are accessible."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.led_status is True
        assert coordinator.audio_status is True
        assert coordinator.secure_screen_status is False


# =============================================================================
# Device Action Tests
# =============================================================================


class TestDeviceActions:
    """Tests for device actions (lock, unlock, settings)."""

    async def test_lock_action(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test lock action calls API correctly."""
        api = MagicMock()
        api.user = MagicMock()
        api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.lock_device = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.lock()

        api.device.lock_device.assert_called_once()

    async def test_unlock_action(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test unlock action calls API correctly."""
        api = MagicMock()
        api.user = MagicMock()
        api.user.get_info = AsyncMock(return_value=MOCK_USER_INFO)
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.unlock_device = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.unlock()

        api.device.unlock_device.assert_called_once()

    async def test_set_led_action(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test set LED action calls API with correct value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.set_led_enabled = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.set_led(True)

        api.device.set_led_enabled.assert_called_once()
        call_args = api.device.set_led_enabled.call_args
        assert call_args[0][1] is True

    async def test_set_audio_action(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test set audio action calls API with correct value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.set_audio_enabled = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.set_audio(False)

        api.device.set_audio_enabled.assert_called_once()
        call_args = api.device.set_audio_enabled.call_args
        assert call_args[0][1] is False

    async def test_set_secure_screen_action(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test set secure screen action calls API with correct value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.set_secure_screen_enabled = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.set_secure_screen(True)

        api.device.set_secure_screen_enabled.assert_called_once()
        call_args = api.device.set_secure_screen_enabled.call_args
        assert call_args[0][1] is True


# =============================================================================
# Boolean Parsing Tests
# =============================================================================


class TestBooleanParsing:
    """Tests for the _parse_bool helper method."""

    def test_parse_bool_true_values(self) -> None:
        """Test parsing various true values."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(True) is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("true") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("True") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("TRUE") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("1") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("yes") is True
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("on") is True

    def test_parse_bool_false_values(self) -> None:
        """Test parsing various false values."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(False) is False
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("false") is False
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("0") is False
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("no") is False
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool("off") is False

    def test_parse_bool_none(self) -> None:
        """Test parsing None returns None."""
        assert KwiksetDeviceDataUpdateCoordinator._parse_bool(None) is None


# =============================================================================
# Data Update Tests
# =============================================================================


class TestDataUpdate:
    """Tests for coordinator data updates."""

    async def test_async_update_data_returns_typed_dict(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test _async_update_data returns properly structured data."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        data = coordinator.data

        # Verify TypedDict structure
        assert "device_info" in data
        assert "door_status" in data
        assert "battery_percentage" in data
        assert "model_number" in data
        assert "serial_number" in data
        assert "firmware_version" in data
        assert "led_status" in data
        assert "audio_status" in data
        assert "secure_screen_status" in data

    async def test_data_update_handles_missing_fields(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test data update handles missing fields gracefully."""
        incomplete_device_info = {
            "deviceid": MOCK_DEVICE_ID,
            "devicename": MOCK_DEVICE_NAME,
            # Missing most fields
        }

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=incomplete_device_info)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()
        data = coordinator.data

        # Should use defaults
        assert data["door_status"] == "Unknown"
        assert data["battery_percentage"] is None
        assert data["led_status"] is None
