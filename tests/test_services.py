"""Tests for the Kwikset access code management services.

Tests the service registration, device resolution, schedule building,
and all access code service handlers.

Quality Scale: Platinum tier - comprehensive service testing infrastructure.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from aiokwikset import DayOfWeek
from aiokwikset import ScheduleType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.kwikset.const import DOMAIN
from custom_components.kwikset.const import SERVICE_CREATE_ACCESS_CODE
from custom_components.kwikset.const import SERVICE_DELETE_ACCESS_CODE
from custom_components.kwikset.const import SERVICE_DELETE_ALL_ACCESS_CODES
from custom_components.kwikset.const import SERVICE_DISABLE_ACCESS_CODE
from custom_components.kwikset.const import SERVICE_EDIT_ACCESS_CODE
from custom_components.kwikset.const import SERVICE_ENABLE_ACCESS_CODE
from custom_components.kwikset.const import SERVICE_LIST_ACCESS_CODES
from custom_components.kwikset.services import _build_schedule
from custom_components.kwikset.services import _resolve_coordinator

from .conftest import MOCK_ACCESS_CODE_RESULT
from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_HOME_ID

# =============================================================================
# Helper to set up a loaded config entry with a registered device
# =============================================================================


async def _setup_entry_with_device(
    hass: HomeAssistant,
    mock_api: MagicMock,
) -> tuple[str, MagicMock]:
    """Set up a config entry and return (ha_device_id, coordinator).

    Returns:
        Tuple of (HA device registry ID, mock coordinator).

    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "user@example.com",
            "conf_home_id": MOCK_HOME_ID,
            "conf_id_token": "mock_id_token",
            "conf_access_token": "mock_access_token",
            "conf_refresh_token": "mock_refresh_token",
        },
        options={"refresh_interval": 30},
        title="My House",
        unique_id=MOCK_HOME_ID,
        version=6,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Look up the HA device registry ID
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_DEVICE_ID)}
    )
    assert device_entry is not None

    coordinator = entry.runtime_data.devices[MOCK_DEVICE_ID]

    return device_entry.id, coordinator


# =============================================================================
# Service Registration Tests
# =============================================================================


class TestServiceRegistration:
    """Tests for service registration/unregistration."""

    async def test_services_registered_on_setup(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test all 6 services are registered after entry setup."""
        await _setup_entry_with_device(hass, mock_api)

        assert hass.services.has_service(DOMAIN, SERVICE_CREATE_ACCESS_CODE)
        assert hass.services.has_service(DOMAIN, SERVICE_EDIT_ACCESS_CODE)
        assert hass.services.has_service(DOMAIN, SERVICE_DISABLE_ACCESS_CODE)
        assert hass.services.has_service(DOMAIN, SERVICE_ENABLE_ACCESS_CODE)
        assert hass.services.has_service(DOMAIN, SERVICE_DELETE_ACCESS_CODE)
        assert hass.services.has_service(DOMAIN, SERVICE_DELETE_ALL_ACCESS_CODES)

    async def test_services_unregistered_on_last_entry_unload(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test services removed when last config entry is unloaded."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "email": "user@example.com",
                "conf_home_id": MOCK_HOME_ID,
                "conf_id_token": "mock_id_token",
                "conf_access_token": "mock_access_token",
                "conf_refresh_token": "mock_refresh_token",
            },
            options={"refresh_interval": 30},
            title="My House",
            unique_id=MOCK_HOME_ID,
            version=6,
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        # Services should be registered
        assert hass.services.has_service(DOMAIN, SERVICE_CREATE_ACCESS_CODE)

        # Unload
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Services should be gone since no entries left
        assert not hass.services.has_service(DOMAIN, SERVICE_CREATE_ACCESS_CODE)


# =============================================================================
# Schedule Builder Tests
# =============================================================================


class TestScheduleBuilder:
    """Tests for _build_schedule helper."""

    def test_build_all_day_schedule(self) -> None:
        """Test building an all-day schedule."""
        data = {"schedule_type": "all_day"}
        schedule = _build_schedule(data)
        assert schedule.schedule_type == ScheduleType.ALL_DAY

    def test_build_date_range_schedule(self) -> None:
        """Test building a date-range schedule with dates and times."""
        data = {
            "schedule_type": "date_range",
            "start_date": datetime.date(2026, 3, 1),
            "end_date": datetime.date(2026, 3, 7),
            "start_time": datetime.time(8, 0),
            "end_time": datetime.time(22, 0),
        }
        schedule = _build_schedule(data)
        assert schedule.schedule_type == ScheduleType.DATE_RANGE
        assert schedule.start_year == 2026
        assert schedule.start_month == 3
        assert schedule.start_day == 1
        assert schedule.end_year == 2026
        assert schedule.end_month == 3
        assert schedule.end_day == 7
        assert schedule.start_hour == 8
        assert schedule.end_hour == 22

    def test_build_weekly_schedule(self) -> None:
        """Test building a weekly schedule with days."""
        data = {
            "schedule_type": "weekly",
            "days_of_week": ["monday", "wednesday", "friday"],
            "start_time": datetime.time(9, 0),
            "end_time": datetime.time(17, 0),
        }
        schedule = _build_schedule(data)
        assert schedule.schedule_type == ScheduleType.WEEKLY
        assert schedule.days_of_week is not None
        assert DayOfWeek.MONDAY in schedule.days_of_week
        assert DayOfWeek.WEDNESDAY in schedule.days_of_week
        assert DayOfWeek.FRIDAY in schedule.days_of_week
        assert DayOfWeek.SUNDAY not in schedule.days_of_week
        assert schedule.start_hour == 9
        assert schedule.end_hour == 17

    def test_build_one_time_unlimited_schedule(self) -> None:
        """Test building one-time unlimited schedule."""
        data = {"schedule_type": "one_time_unlimited"}
        schedule = _build_schedule(data)
        assert schedule.schedule_type == ScheduleType.ONE_TIME_UNLIMITED

    def test_build_one_time_24_hour_schedule(self) -> None:
        """Test building one-time 24-hour schedule."""
        data = {"schedule_type": "one_time_24_hour"}
        schedule = _build_schedule(data)
        assert schedule.schedule_type == ScheduleType.ONE_TIME_24_HOUR

    def test_date_range_missing_dates_raises(self) -> None:
        """Test date_range without required dates raises error."""
        data = {"schedule_type": "date_range"}
        with pytest.raises(HomeAssistantError):
            _build_schedule(data)

    def test_weekly_missing_days_raises(self) -> None:
        """Test weekly without days_of_week raises error."""
        data = {"schedule_type": "weekly"}
        with pytest.raises(HomeAssistantError):
            _build_schedule(data)


# =============================================================================
# Device Resolution Tests
# =============================================================================


class TestDeviceResolution:
    """Tests for _resolve_coordinator helper."""

    async def test_resolve_valid_device(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test resolving a valid HA device ID to coordinator."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        result = _resolve_coordinator(hass, ha_device_id)
        assert result is coordinator

    async def test_resolve_unknown_device_raises(self, hass: HomeAssistant) -> None:
        """Test HomeAssistantError for unknown device ID."""
        with pytest.raises(HomeAssistantError):
            _resolve_coordinator(hass, "nonexistent_device_id")

    async def test_resolve_non_kwikset_device_raises(self, hass: HomeAssistant) -> None:
        """Test HomeAssistantError for non-Kwikset device."""
        device_registry = dr.async_get(hass)
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(domain="other_domain")
        entry.add_to_hass(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("other_domain", "some_id")},
        )

        with pytest.raises(HomeAssistantError):
            _resolve_coordinator(hass, device_entry.id)

    async def test_resolve_unloaded_device_raises(self, hass: HomeAssistant) -> None:
        """Test HomeAssistantError when device exists but integration not loaded."""
        device_registry = dr.async_get(hass)
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "orphan_device_id")},
        )

        with pytest.raises(HomeAssistantError):
            _resolve_coordinator(hass, device_entry.id)


# =============================================================================
# Create Access Code Tests
# =============================================================================


class TestCreateAccessCode:
    """Tests for kwikset.create_access_code service."""

    async def test_create_all_day_code(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test creating an all-day access code."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)

        coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "1234",
                "name": "Guest",
                "schedule_type": "all_day",
            },
            blocking=True,
        )

        coordinator.create_access_code.assert_called_once()
        call_kwargs = coordinator.create_access_code.call_args.kwargs
        assert call_kwargs["code"] == "1234"
        assert call_kwargs["name"] == "Guest"
        assert call_kwargs["slot"] == 0

    async def test_create_date_range_code(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test creating a date-range scheduled code."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "5678",
                "name": "Contractor",
                "schedule_type": "date_range",
                "start_date": "2026-03-01",
                "end_date": "2026-03-07",
                "start_time": "08:00:00",
                "end_time": "17:00:00",
            },
            blocking=True,
        )

        coordinator.create_access_code.assert_called_once()
        schedule = coordinator.create_access_code.call_args.kwargs["schedule"]
        assert schedule.schedule_type == ScheduleType.DATE_RANGE

    async def test_create_weekly_code(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test creating a weekly scheduled code."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "9012",
                "name": "Cleaner",
                "schedule_type": "weekly",
                "days_of_week": ["monday", "wednesday", "friday"],
                "start_time": "09:00:00",
                "end_time": "17:00:00",
            },
            blocking=True,
        )

        coordinator.create_access_code.assert_called_once()
        schedule = coordinator.create_access_code.call_args.kwargs["schedule"]
        assert schedule.schedule_type == ScheduleType.WEEKLY

    async def test_create_with_specific_slot(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test creating code in a specific slot."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "1234",
                "name": "Friend",
                "schedule_type": "all_day",
                "slot": 5,
            },
            blocking=True,
        )

        assert coordinator.create_access_code.call_args.kwargs["slot"] == 5

    async def test_create_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError with translation_key on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.create_access_code = AsyncMock(
            side_effect=HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            )
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "code": "1234",
                    "name": "Test",
                    "schedule_type": "all_day",
                },
                blocking=True,
            )

    async def test_create_wraps_unexpected_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test unexpected errors wrapped in HomeAssistantError."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.create_access_code = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "code": "1234",
                    "name": "Test",
                    "schedule_type": "all_day",
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "create_access_code_failed"


# =============================================================================
# Edit Access Code Tests
# =============================================================================


class TestEditAccessCode:
    """Tests for kwikset.edit_access_code service."""

    async def test_edit_access_code(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test editing an access code."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.edit_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_EDIT_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "5678",
                "name": "Updated Guest",
                "schedule_type": "all_day",
                "slot": 3,
            },
            blocking=True,
        )

        coordinator.edit_access_code.assert_called_once()
        call_kwargs = coordinator.edit_access_code.call_args.kwargs
        assert call_kwargs["code"] == "5678"
        assert call_kwargs["name"] == "Updated Guest"
        assert call_kwargs["slot"] == 3

    async def test_edit_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.edit_access_code = AsyncMock(side_effect=RuntimeError("API error"))

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_EDIT_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "code": "5678",
                    "name": "Test",
                    "schedule_type": "all_day",
                    "slot": 3,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "edit_access_code_failed"


# =============================================================================
# Disable/Enable Access Code Tests
# =============================================================================


class TestDisableEnableAccessCode:
    """Tests for kwikset.disable_access_code and kwikset.enable_access_code."""

    async def test_disable_access_code_with_overrides(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test disabling an access code with all fields provided (override path)."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.disable_access_code = AsyncMock(
            return_value=MOCK_ACCESS_CODE_RESULT
        )
        coordinator.get_tracked_code = MagicMock(return_value=None)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISABLE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "1234",
                "name": "Guest",
                "schedule_type": "all_day",
                "slot": 3,
            },
            blocking=True,
        )

        coordinator.disable_access_code.assert_called_once()
        call_kwargs = coordinator.disable_access_code.call_args.kwargs
        assert call_kwargs["code"] == "1234"
        assert call_kwargs["slot"] == 3

    async def test_disable_access_code_slot_only(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test disabling by slot number only, using stored metadata."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.disable_access_code = AsyncMock(
            return_value=MOCK_ACCESS_CODE_RESULT
        )
        coordinator.get_tracked_code = MagicMock(
            return_value={
                "slot": 3,
                "name": "Guest",
                "code": "5678",
                "schedule_type": "all_day",
                "enabled": True,
                "source": "ha",
                "created_at": None,
                "last_updated": None,
            }
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISABLE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "slot": 3,
            },
            blocking=True,
        )

        coordinator.disable_access_code.assert_called_once()
        call_kwargs = coordinator.disable_access_code.call_args.kwargs
        assert call_kwargs["code"] == "5678"
        assert call_kwargs["name"] == "Guest"
        assert call_kwargs["slot"] == 3

    async def test_disable_access_code_not_tracked_no_code(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test error when slot not tracked and no code provided."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.get_tracked_code = MagicMock(return_value=None)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DISABLE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "slot": 3,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "access_code_not_tracked"

    async def test_enable_access_code_with_overrides(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test enabling an access code with all fields provided (override path)."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        coordinator.get_tracked_code = MagicMock(return_value=None)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "1234",
                "name": "Guest",
                "schedule_type": "all_day",
                "slot": 3,
            },
            blocking=True,
        )

        coordinator.enable_access_code.assert_called_once()
        call_kwargs = coordinator.enable_access_code.call_args.kwargs
        assert call_kwargs["code"] == "1234"
        assert call_kwargs["slot"] == 3

    async def test_enable_access_code_slot_only(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test enabling by slot number only, using stored metadata."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.enable_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)
        coordinator.get_tracked_code = MagicMock(
            return_value={
                "slot": 5,
                "name": "Temp Code",
                "code": "9999",
                "schedule_type": "all_day",
                "enabled": False,
                "source": "ha",
                "created_at": None,
                "last_updated": None,
            }
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "slot": 5,
            },
            blocking=True,
        )

        coordinator.enable_access_code.assert_called_once()
        call_kwargs = coordinator.enable_access_code.call_args.kwargs
        assert call_kwargs["code"] == "9999"
        assert call_kwargs["name"] == "Temp Code"
        assert call_kwargs["slot"] == 5

    async def test_disable_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.disable_access_code = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        coordinator.get_tracked_code = MagicMock(return_value=None)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DISABLE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "code": "1234",
                    "name": "Guest",
                    "schedule_type": "all_day",
                    "slot": 3,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "disable_access_code_failed"

    async def test_enable_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.enable_access_code = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        coordinator.get_tracked_code = MagicMock(return_value=None)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ENABLE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "code": "1234",
                    "name": "Guest",
                    "schedule_type": "all_day",
                    "slot": 3,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "enable_access_code_failed"


# =============================================================================
# Delete Access Code Tests
# =============================================================================


class TestDeleteAccessCode:
    """Tests for kwikset.delete_access_code and kwikset.delete_all_access_codes."""

    async def test_delete_by_slot(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test deleting a specific access code by slot."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.delete_access_code = AsyncMock(return_value={"data": []})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "slot": 3,
            },
            blocking=True,
        )

        coordinator.delete_access_code.assert_called_once()
        assert coordinator.delete_access_code.call_args.kwargs["slot"] == 3

    async def test_delete_all(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test deleting all access codes."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.delete_all_access_codes = AsyncMock(return_value={"data": []})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_ALL_ACCESS_CODES,
            {
                "device_id": ha_device_id,
            },
            blocking=True,
        )

        coordinator.delete_all_access_codes.assert_called_once()

    async def test_delete_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.delete_access_code = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_ACCESS_CODE,
                {
                    "device_id": ha_device_id,
                    "slot": 3,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "delete_access_code_failed"

    async def test_delete_all_raises_on_api_error(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError on API failure."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)
        coordinator.delete_all_access_codes = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_ALL_ACCESS_CODES,
                {
                    "device_id": ha_device_id,
                },
                blocking=True,
            )

        assert exc_info.value.translation_key == "delete_all_access_codes_failed"

    async def test_delete_device_not_found(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError when device not found."""
        await _setup_entry_with_device(hass, mock_api)

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_ACCESS_CODE,
                {
                    "device_id": "nonexistent_device",
                    "slot": 1,
                },
                blocking=True,
            )


# =============================================================================
# List Access Codes Tests
# =============================================================================


class TestListAccessCodes:
    """Tests for the list_access_codes service."""

    async def test_list_empty(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test listing access codes with no codes tracked."""
        ha_device_id, _coordinator = await _setup_entry_with_device(hass, mock_api)

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert result["total"] == 0
        assert result["access_codes"] == []

    async def test_list_with_ha_managed_codes(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test listing access codes after creating some via service."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)

        # Track a code manually
        await coordinator.async_track_access_code(
            slot=1, name="Guest", code="1234", schedule_type="all_day"
        )
        await coordinator.async_track_access_code(
            slot=5, name="Cleaner", code="5678", schedule_type="weekly", enabled=False
        )

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert result["total"] == 2
        codes = result["access_codes"]
        assert len(codes) == 2
        assert codes[0]["slot"] == 1
        assert codes[0]["name"] == "Guest"
        assert codes[0]["source"] == "ha"
        assert codes[0]["enabled"] is True
        assert codes[1]["slot"] == 5
        assert codes[1]["name"] == "Cleaner"
        assert codes[1]["enabled"] is False

    async def test_list_device_not_found(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test HomeAssistantError when device is not found."""
        await _setup_entry_with_device(hass, mock_api)

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_LIST_ACCESS_CODES,
                {"device_id": "nonexistent_device"},
                blocking=True,
                return_response=True,
            )

    async def test_create_then_list_round_trip(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test creating a code and seeing it in list_access_codes."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)

        coordinator.create_access_code = AsyncMock(return_value=MOCK_ACCESS_CODE_RESULT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_ACCESS_CODE,
            {
                "device_id": ha_device_id,
                "code": "1234",
                "name": "Test Code",
                "schedule_type": "all_day",
                "slot": 3,
            },
            blocking=True,
        )

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert result["total"] >= 1
        slots = [c["slot"] for c in result["access_codes"]]
        assert 3 in slots

    async def test_delete_then_list_round_trip(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test deleting a code and verifying it's gone from list."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)

        # Track then delete
        await coordinator.async_track_access_code(
            slot=2, name="Temp", code="4321", schedule_type="all_day"
        )
        coordinator.delete_access_code = AsyncMock(return_value={})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_ACCESS_CODE,
            {"device_id": ha_device_id, "slot": 2},
            blocking=True,
        )

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        slots = [c["slot"] for c in result["access_codes"]]
        assert 2 not in slots

    async def test_delete_all_clears_tracking(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test delete_all clears all tracked codes."""
        ha_device_id, coordinator = await _setup_entry_with_device(hass, mock_api)

        # Track multiple codes
        await coordinator.async_track_access_code(
            slot=1, name="Code1", code="1111", schedule_type="all_day"
        )
        await coordinator.async_track_access_code(
            slot=2, name="Code2", code="2222", schedule_type="weekly"
        )
        coordinator.delete_all_access_codes = AsyncMock(return_value={})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_ALL_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
        )

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_ACCESS_CODES,
            {"device_id": ha_device_id},
            blocking=True,
            return_response=True,
        )

        assert result is not None
        assert result["total"] == 0
