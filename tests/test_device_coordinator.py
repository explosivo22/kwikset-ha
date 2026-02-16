"""Tests for the KwiksetDeviceDataUpdateCoordinator.

Tests the device coordinator including:
- API call retry logic
- Device property access
- Lock/unlock and settings actions
- Error handling and recovery

Quality Scale: Platinum tier - coordinator is the central data management component.
"""

from __future__ import annotations

import asyncio
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

from .conftest import MOCK_ACCESS_CODE_RESULT
from .conftest import MOCK_DEVICE_HISTORY
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

        # Mock async_request_refresh to avoid lingering debouncer timers
        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock):
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

        # Mock async_request_refresh to avoid lingering debouncer timers
        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock):
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

        # Mock async_request_refresh to avoid lingering debouncer timers
        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock):
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

        # Mock async_request_refresh to avoid lingering debouncer timers
        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock):
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

        # Mock async_request_refresh to avoid lingering debouncer timers
        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock):
            await coordinator.set_secure_screen(True)

        api.device.set_secure_screen_enabled.assert_called_once()
        call_args = api.device.set_secure_screen_enabled.call_args
        assert call_args[0][1] is True


# =============================================================================
# Access Code Action Tests
# =============================================================================


class TestAccessCodeActions:
    """Tests for access code coordinator methods."""

    async def test_create_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test create_access_code calls API correctly."""
        from aiokwikset import AccessCodeSchedule
        from aiokwikset import ScheduleType

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        schedule = AccessCodeSchedule(schedule_type=ScheduleType.ALL_DAY)
        result = await coordinator.create_access_code(
            code="1234",
            name="Guest",
            schedule=schedule,
            slot=0,
        )

        api.device.create_access_code.assert_called_once_with(
            MOCK_DEVICE_ID,
            "1234",
            "Guest",
            schedule,
            slot=0,
            enabled=True,
        )
        assert result.token == "mock_token_abc123"

    async def test_disable_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test disable_access_code calls API correctly."""
        from aiokwikset import AccessCodeSchedule
        from aiokwikset import ScheduleType

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.disable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        schedule = AccessCodeSchedule(schedule_type=ScheduleType.ALL_DAY)
        result = await coordinator.disable_access_code(
            code="1234",
            name="Guest",
            schedule=schedule,
            slot=3,
        )

        api.device.disable_access_code.assert_called_once_with(
            MOCK_DEVICE_ID,
            "1234",
            "Guest",
            schedule,
            3,
        )
        assert result.token == "mock_token_abc123"

    async def test_enable_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test enable_access_code calls API correctly."""
        from aiokwikset import AccessCodeSchedule
        from aiokwikset import ScheduleType

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        schedule = AccessCodeSchedule(schedule_type=ScheduleType.ALL_DAY)
        result = await coordinator.enable_access_code(
            code="1234",
            name="Guest",
            schedule=schedule,
            slot=3,
        )

        api.device.enable_access_code.assert_called_once_with(
            MOCK_DEVICE_ID,
            "1234",
            "Guest",
            schedule,
            3,
        )
        assert result.token == "mock_token_abc123"

    async def test_delete_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test delete_access_code calls API correctly."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.delete_access_code = AsyncMock(return_value={"data": []})

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        result = await coordinator.delete_access_code(slot=5)

        api.device.delete_access_code.assert_called_once_with(
            MOCK_DEVICE_ID,
            5,
        )
        assert result == {"data": []}

    async def test_delete_all_access_codes(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test delete_all_access_codes calls API correctly."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.delete_all_access_codes = AsyncMock(return_value={"data": []})

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        result = await coordinator.delete_all_access_codes()

        api.device.delete_all_access_codes.assert_called_once_with(
            MOCK_DEVICE_ID,
        )
        assert result == {"data": []}

    async def test_create_access_code_auth_error(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test auth error handling in create_access_code."""
        from aiokwikset import AccessCodeSchedule
        from aiokwikset import ScheduleType

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.create_access_code = AsyncMock(
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

        await coordinator.async_config_entry_first_refresh()

        schedule = AccessCodeSchedule(schedule_type=ScheduleType.ALL_DAY)

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.create_access_code(
                code="1234",
                name="Guest",
                schedule=schedule,
            )

    async def test_create_access_code_request_error_retries(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test retry logic in create_access_code."""
        from aiokwikset import AccessCodeSchedule
        from aiokwikset import ScheduleType

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )
        api.device.create_access_code = AsyncMock(
            side_effect=[
                RequestError("Network error"),
                RequestError("Network error"),
                MOCK_ACCESS_CODE_RESULT,
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

        await coordinator.async_config_entry_first_refresh()

        schedule = AccessCodeSchedule(schedule_type=ScheduleType.ALL_DAY)

        with patch(
            "custom_components.kwikset.device.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await coordinator.create_access_code(
                code="1234",
                name="Guest",
                schedule=schedule,
            )

        assert result.token == "mock_token_abc123"
        assert api.device.create_access_code.call_count == 3


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


# =============================================================================
# History Property Tests
# =============================================================================


class TestHistoryProperties:
    """Tests for coordinator history properties."""

    async def test_history_events_property_returns_events(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test history_events property returns the list of events."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert len(coordinator.history_events) == 2
        assert coordinator.history_events[0]["event"] == "Locked"

    async def test_last_event_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test last_event returns the most recent event description."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_event == "Locked"

    async def test_last_event_user_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test last_event_user returns the user of the most recent event."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_event_user == "John Doe"

    async def test_last_event_type_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test last_event_type returns the event type."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_event_type == "Mobile ( WiFi, LTE, ETC)"

    async def test_last_event_timestamp_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test last_event_timestamp returns the unix epoch timestamp."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_event_timestamp == 1770928208

    async def test_last_event_category_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test last_event_category returns the event category."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_event_category == "Lock Mechanism"

    async def test_total_events_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test total_events returns the count of fetched events."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.total_events == 2

    async def test_history_properties_empty_when_no_history(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test all history properties return None/0/[] when no history."""
        empty_history = {"data": [], "total": 0, "issues": []}
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=empty_history)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert coordinator.history_events == []
        assert coordinator.last_event is None
        assert coordinator.last_event_user is None
        assert coordinator.last_event_type is None
        assert coordinator.last_event_timestamp is None
        assert coordinator.last_event_category is None
        assert coordinator.total_events == 0

    async def test_history_fetch_failure_does_not_break_update(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that history fetch failure doesn't break the main data update."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            side_effect=Exception("History API error")
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # Should NOT raise — history failure is caught
        await coordinator.async_config_entry_first_refresh()

        # Core device data should still be available
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85
        # History should be empty (no cached data on first failure)
        assert coordinator.history_events == []

    async def test_history_timeout_preserves_cached_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that history timeout preserves previously cached events."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # First refresh succeeds — populates cache
        await coordinator.async_config_entry_first_refresh()
        assert len(coordinator.history_events) == 2

        # Now make history time out
        async def _slow_history(*args: object, **kwargs: object) -> None:
            await asyncio.sleep(60)

        api.device.get_device_history = _slow_history

        await coordinator.async_refresh()

        # Core data still refreshed, history preserved from cache
        assert coordinator.data["door_status"] == "Locked"
        assert len(coordinator.history_events) == 2

    async def test_history_request_error_preserves_cached_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that RequestError on history preserves previously cached events."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # First refresh succeeds
        await coordinator.async_config_entry_first_refresh()
        assert len(coordinator.history_events) == 2

        # Subsequent history fetch raises RequestError (e.g. 504)
        api.device.get_device_history = AsyncMock(
            side_effect=RequestError("504 Gateway Timeout")
        )

        await coordinator.async_refresh()

        # Cached history preserved
        assert len(coordinator.history_events) == 2
        assert coordinator.history_events[0]["event"] == "Locked"

    async def test_history_fetch_retries_limited_times(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that history fetch retries up to HISTORY_MAX_RETRY_ATTEMPTS."""
        from custom_components.kwikset.const import HISTORY_MAX_RETRY_ATTEMPTS

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        history_mock = AsyncMock(side_effect=RequestError("504 Gateway Timeout"))
        api.device.get_device_history = history_mock

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # History should be called exactly HISTORY_MAX_RETRY_ATTEMPTS times
        assert history_mock.call_count == HISTORY_MAX_RETRY_ATTEMPTS

    async def test_data_update_includes_history_events(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test coordinator data dict includes history_events field."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        assert "history_events" in coordinator.data
        assert len(coordinator.data["history_events"]) == 2


# =============================================================================
# Real-Time Event Handling Tests
# =============================================================================


class TestHandleRealtimeEvent:
    """Tests for handle_realtime_event method."""

    async def test_handle_realtime_event_updates_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test coordinator data is updated from real-time event."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Verify initial state
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85

        # Simulate real-time event with updated status and battery
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": "Unlocked",
            "batterypercentage": 72,
        }
        with patch.object(coordinator, "async_request_refresh"):
            coordinator.handle_realtime_event(event_data)

        # Verify data was updated
        assert coordinator.data["door_status"] == "Unlocked"
        assert coordinator.data["battery_percentage"] == 72

    async def test_handle_realtime_event_partial_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test only present non-None fields are updated, others retain previous values."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Verify initial state
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85
        assert coordinator.data["led_status"] is True

        # Send event with only door status — battery and LED should be preserved
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": "Unlocked",
        }
        with patch.object(coordinator, "async_request_refresh"):
            coordinator.handle_realtime_event(event_data)

        assert coordinator.data["door_status"] == "Unlocked"
        assert coordinator.data["battery_percentage"] == 85  # Preserved
        assert coordinator.data["led_status"] is True  # Preserved

    async def test_handle_realtime_event_none_values_skipped(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that None values in event data do not overwrite existing data."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Verify initial state
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85
        assert coordinator.data["led_status"] is True
        assert coordinator.data["audio_status"] is True
        assert coordinator.data["secure_screen_status"] is False

        # Real-world event: setting change sends None for unrelated fields
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": None,
            "batterypercentage": None,
            "ledstatus": None,
            "audiostatus": "false",
            "securescreenstatus": "true",
        }
        coordinator.handle_realtime_event(event_data)

        # None values should NOT overwrite existing data
        assert coordinator.data["door_status"] == "Locked"  # Preserved
        assert coordinator.data["battery_percentage"] == 85  # Preserved
        assert coordinator.data["led_status"] is True  # Preserved
        # Non-None values should be applied
        assert coordinator.data["audio_status"] is False
        assert coordinator.data["secure_screen_status"] is True

    async def test_handle_realtime_event_unknown_fields_ignored(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test unknown fields in event data don't cause errors."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Send event with unknown fields — should not raise
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "unknownfield": "some_value",
            "anotherfield": 42,
        }
        coordinator.handle_realtime_event(event_data)

        # Data should remain unchanged for known fields
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85

    async def test_handle_realtime_event_no_initial_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test event is ignored when coordinator has no initial data."""
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

        # Don't do first refresh — coordinator.data is None
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": "Unlocked",
        }

        # Should not raise
        coordinator.handle_realtime_event(event_data)

        # Data should still be None
        assert coordinator.data is None

    async def test_handle_realtime_event_lock_status_fields(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test various lock-related fields are properly mapped in handle_realtime_event."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Verify initial state from MOCK_DEVICE_INFO
        assert coordinator.data["door_status"] == "Locked"
        assert coordinator.data["battery_percentage"] == 85
        assert coordinator.data["led_status"] is True
        assert coordinator.data["audio_status"] is True
        assert coordinator.data["secure_screen_status"] is False

        # Patch async_request_refresh to avoid RuntimeWarning about
        # unawaited coroutines — door status changes trigger a refresh.
        with patch.object(coordinator, "async_request_refresh"):
            # Test doorstatus key (polling key) updates door_status
            coordinator.handle_realtime_event({"doorstatus": "Unlocked"})
            assert coordinator.data["door_status"] == "Unlocked"

            # Test devicestatus key (websocket-specific) overrides doorstatus
            coordinator.handle_realtime_event(
                {"doorstatus": "Locked", "devicestatus": "Jammed"}
            )
            assert coordinator.data["door_status"] == "Jammed"

            # Test battery update
            coordinator.handle_realtime_event({"batterypercentage": 50})
            assert coordinator.data["battery_percentage"] == 50

            # Test LED status update
            coordinator.handle_realtime_event({"ledstatus": "false"})
            assert coordinator.data["led_status"] is False

            # Test audio status update
            coordinator.handle_realtime_event({"audiostatus": "true"})
            assert coordinator.data["audio_status"] is True

            # Test secure screen status update
            coordinator.handle_realtime_event({"securescreenstatus": "true"})
            assert coordinator.data["secure_screen_status"] is True

    async def test_handle_realtime_event_requests_refresh_on_door_change(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test that a door status change via websocket schedules a coordinator refresh.

        The websocket does not carry event history, so the coordinator must
        request an immediate refresh to fetch real history from the REST API.
        """
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Initially no history events
        assert coordinator.data["history_events"] == []

        # Simulate websocket lock event (door status changes)
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": "Unlocked",
            "devicename": "Front Door",
            "email": "test@example.com",
        }

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            coordinator.handle_realtime_event(event_data)

            # Door status changed → refresh must be requested
            mock_refresh.assert_called_once()

        # Door status should be updated immediately via async_set_updated_data
        assert coordinator.data["door_status"] == "Unlocked"
        # History events should NOT contain synthetic entries — the refresh
        # will fetch real history from the REST API
        assert coordinator.data["history_events"] == []

    async def test_handle_realtime_event_no_refresh_on_same_status(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test no refresh is requested when door status hasn't changed."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(
            return_value={"data": [], "total": 0, "issues": []}
        )

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        await coordinator.async_config_entry_first_refresh()

        # Status is already "Locked" — send same status via websocket
        event_data = {
            "deviceid": MOCK_DEVICE_ID,
            "devicestatus": "Locked",
        }

        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            coordinator.handle_realtime_event(event_data)

            # Status didn't change → no refresh needed
            mock_refresh.assert_not_called()

        # History events should still be empty — no change
        assert coordinator.data["history_events"] == []


# =============================================================================
# Access Code Tracking Tests
# =============================================================================


class TestAccessCodeTracking:
    """Tests for access code metadata tracking and slot parsing."""

    async def test_track_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test tracking an HA-managed access code."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        await coordinator.async_track_access_code(
            slot=5, name="Guest", code="1234", schedule_type="all_day"
        )

        codes = coordinator.access_codes
        assert 5 in codes
        assert codes[5]["name"] == "Guest"
        assert codes[5]["source"] == "ha"
        assert codes[5]["enabled"] is True
        assert codes[5]["schedule_type"] == "all_day"
        assert codes[5]["created_at"] is not None
        mock_store.async_save.assert_called()

    async def test_update_access_code_enabled(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test updating enabled status of a tracked code."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        await coordinator.async_track_access_code(
            slot=3, name="Cleaner", code="5678", schedule_type="weekly"
        )
        await coordinator.async_update_access_code_enabled(slot=3, enabled=False)

        codes = coordinator.access_codes
        assert codes[3]["enabled"] is False

    async def test_remove_access_code(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test removing a tracked access code."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        await coordinator.async_track_access_code(
            slot=2, name="Temp", code="4321", schedule_type="all_day"
        )
        assert 2 in coordinator.access_codes

        await coordinator.async_remove_access_code(slot=2)
        assert 2 not in coordinator.access_codes

    async def test_remove_all_access_codes(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test removing all tracked access codes for a device."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        await coordinator.async_track_access_code(
            slot=1, name="A", code="1111", schedule_type="all_day"
        )
        await coordinator.async_track_access_code(
            slot=2, name="B", code="2222", schedule_type="weekly"
        )

        assert coordinator.total_access_codes == 2

        await coordinator.async_remove_all_access_codes()

        assert coordinator.total_access_codes == 0
        assert coordinator.occupied_slots == []

    async def test_total_access_codes_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test total_access_codes returns correct count."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=None,
            access_code_data={},
        )

        assert coordinator.total_access_codes == 0

    async def test_occupied_slots_property(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test occupied_slots returns sorted list."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        await coordinator.async_track_access_code(
            slot=5, name="B", code="5555", schedule_type="all_day"
        )
        await coordinator.async_track_access_code(
            slot=1, name="A", code="1111", schedule_type="all_day"
        )

        assert coordinator.occupied_slots == [1, 5]

    async def test_access_codes_merges_device_and_ha_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test access_codes merges device-reported and HA-managed data."""
        from custom_components.kwikset.device import AccessCodeSlotData

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        # Simulate device-reported slot
        coordinator._device_reported_slots = {
            10: AccessCodeSlotData(
                slot=10, occupied=True, crc_token=None, raw_data="test"
            )
        }

        # Track an HA-managed code
        await coordinator.async_track_access_code(
            slot=3, name="HA Code", code="3333", schedule_type="all_day"
        )

        codes = coordinator.access_codes
        assert 3 in codes
        assert codes[3]["source"] == "ha"
        assert codes[3]["name"] == "HA Code"
        assert 10 in codes
        assert codes[10]["source"] == "device"
        assert codes[10]["name"] == ""

    async def test_ha_metadata_overrides_device_slot(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test HA metadata overrides device-reported data for same slot."""
        from custom_components.kwikset.device import AccessCodeSlotData

        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)
        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
            access_code_store=mock_store,
            access_code_data={},
        )

        # Slot 5 reported by both device and HA
        coordinator._device_reported_slots = {
            5: AccessCodeSlotData(slot=5, occupied=True, crc_token=None, raw_data="dev")
        }
        await coordinator.async_track_access_code(
            slot=5, name="My Code", code="5555", schedule_type="weekly"
        )

        codes = coordinator.access_codes
        assert codes[5]["source"] == "ha"
        assert codes[5]["name"] == "My Code"
        assert codes[5]["schedule_type"] == "weekly"


class TestSlotParsing:
    """Tests for device data slot parsing methods."""

    async def test_parse_bitmap_empty(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test bitmap parsing with None value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = coordinator._parse_access_code_bitmap(None, max_slots=64)
        assert result == {}

    async def test_parse_bitmap_valid_hex(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test bitmap parsing with valid hex string."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # 0x05 = binary 101 → slots 0 and 2 occupied
        result = coordinator._parse_access_code_bitmap("05", max_slots=8)
        assert 0 in result
        assert 2 in result
        assert 1 not in result

    async def test_parse_bitmap_invalid(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test bitmap parsing with invalid value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = coordinator._parse_access_code_bitmap("not_hex", max_slots=8)
        assert result == {}

    async def test_parse_access_code_crc_empty(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test CRC parsing with empty value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = coordinator._parse_access_code_crc(None)
        assert result == {}

        result = coordinator._parse_access_code_crc("")
        assert result == {}

    async def test_discover_device_slots_empty(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test slot discovery with no access code fields."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        # MOCK_DEVICE_INFO doesn't have access code fields
        result = coordinator._discover_device_slots(MOCK_DEVICE_INFO)
        assert result == {}

    async def test_discover_device_slots_with_bitmap(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test slot discovery with bitmap data."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        info_with_bitmap = {
            **MOCK_DEVICE_INFO,
            "accesscodeeight": "03",  # slots 0 and 1
        }
        result = coordinator._discover_device_slots(info_with_bitmap)
        assert 0 in result
        assert 1 in result

    async def test_parse_access_code_by_index_none(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test accesscodebyindex parsing with None value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = coordinator._parse_access_code_by_index(None)
        assert result == {}

    async def test_parse_access_code_by_index_dict(
        self,
        hass: HomeAssistant,
        mock_config_entry: MagicMock,
    ) -> None:
        """Test accesscodebyindex parsing with dict value."""
        api = MagicMock()
        api.device = MagicMock()
        api.device.get_device_info = AsyncMock(return_value=MOCK_DEVICE_INFO)
        api.device.get_device_history = AsyncMock(return_value=MOCK_DEVICE_HISTORY)

        coordinator = KwiksetDeviceDataUpdateCoordinator(
            hass=hass,
            api_client=api,
            device_id=MOCK_DEVICE_ID,
            device_name=MOCK_DEVICE_NAME,
            update_interval=30,
            config_entry=mock_config_entry,
        )

        result = coordinator._parse_access_code_by_index(
            {"0": "some_data", "3": "other_data", "5": None}
        )
        assert 0 in result
        assert result[0]["occupied"] is True
        assert 3 in result
        assert 5 in result
        assert result[5]["occupied"] is False  # None value = not occupied
