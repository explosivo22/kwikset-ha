"""Tests for Kwikset integration setup."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.kwikset import (
    KwiksetRuntimeData,
    _async_options_updated,
    _async_update_devices,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.kwikset.const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

from .conftest import (
    MOCK_DEVICES,
)


async def test_setup_entry_success(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.kwikset.KwiksetDeviceDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert hasattr(mock_config_entry, "runtime_data")
    assert isinstance(mock_config_entry.runtime_data, KwiksetRuntimeData)


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test setup fails on authentication error."""
    from aiokwikset.api import Unauthenticated

    mock_api.async_renew_access_token.side_effect = Unauthenticated("Invalid token")
    mock_config_entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, mock_config_entry)


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test setup fails on connection error."""
    from aiokwikset.errors import RequestError

    mock_api.async_renew_access_token.side_effect = RequestError("Connection failed")
    mock_config_entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)


async def test_setup_entry_token_refresh(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test that tokens are refreshed and saved."""
    # Set new tokens after refresh
    mock_api.access_token = "new_access_token"
    mock_api.refresh_token = "new_refresh_token"

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.kwikset.KwiksetDeviceDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        await async_setup_entry(hass, mock_config_entry)

    # Verify entry was updated with new tokens
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new_access_token"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new_refresh_token"


async def test_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test successful unload of config entry."""
    # Set up the runtime_data
    mock_config_entry.runtime_data = KwiksetRuntimeData(
        client=MagicMock(),
        devices={},
        known_devices=set(),
    )

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ):
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True


async def test_unload_entry_failure(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test failed unload of config entry."""
    mock_config_entry.runtime_data = KwiksetRuntimeData(
        client=MagicMock(),
        devices={},
        known_devices=set(),
    )

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is False


async def test_migrate_entry_v1_to_v4(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test migration from version 1 to 4."""
    mock_config_entry.version = 1
    mock_config_entry.data = {
        CONF_REFRESH_TOKEN: "old_refresh_token",
    }

    result = await async_migrate_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.version == 4


async def test_migrate_entry_v2_to_v4(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test migration from version 2 to 4."""
    mock_config_entry.version = 2
    mock_config_entry.data = {
        CONF_REFRESH_TOKEN: "old_refresh_token",
    }

    result = await async_migrate_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.version >= 3


async def test_migrate_entry_v3_to_v4(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test migration from version 3 to 4."""
    mock_config_entry.version = 3
    mock_config_entry.data = {
        CONF_ACCESS_TOKEN: "access_token",
        CONF_REFRESH_TOKEN: "refresh_token",
    }

    result = await async_migrate_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.version == 4


async def test_update_devices_discovers_new(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test that new devices are discovered."""
    # Set up with one known device using runtime_data
    mock_config_entry.runtime_data = KwiksetRuntimeData(
        client=mock_api,
        devices={},
        known_devices={"device_123"},
    )

    # API returns two devices (one new)
    mock_api.device.get_devices.return_value = MOCK_DEVICES

    events_fired = []
    hass.bus.async_fire = lambda event, data: events_fired.append((event, data))

    with patch(
        "custom_components.kwikset.KwiksetDeviceDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with patch("custom_components.kwikset.dr"):
            await _async_update_devices(hass, mock_config_entry)

    # Should have fired event for new device
    assert len(events_fired) == 1
    assert events_fired[0][0] == f"{DOMAIN}_new_device"
    assert "device_456" in events_fired[0][1]["device_ids"]


async def test_update_devices_removes_stale(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Test that stale devices are removed."""
    mock_coordinator = MagicMock()

    # Set up with two known devices using runtime_data
    mock_config_entry.runtime_data = KwiksetRuntimeData(
        client=mock_api,
        devices={
            "device_123": mock_coordinator,
            "device_old": mock_coordinator,
        },
        known_devices={"device_123", "device_old"},
    )

    # API returns only one device
    mock_api.device.get_devices.return_value = [MOCK_DEVICES[0]]

    with patch("custom_components.kwikset.dr") as mock_dr:
        mock_registry = MagicMock()
        mock_registry.async_get_device.return_value = MagicMock(id="device_id")
        mock_dr.async_get.return_value = mock_registry

        await _async_update_devices(hass, mock_config_entry)

    # Device should be removed from runtime_data
    assert "device_old" not in mock_config_entry.runtime_data.known_devices


async def test_options_updated_changes_interval(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that options update changes coordinator interval."""
    mock_coordinator = MagicMock()
    mock_coordinator.update_interval = timedelta(seconds=30)
    mock_coordinator.async_request_refresh = AsyncMock()

    # Set up using runtime_data
    mock_config_entry.runtime_data = KwiksetRuntimeData(
        client=MagicMock(),
        devices={"device_123": mock_coordinator},
        known_devices={"device_123"},
    )

    # Change interval to 45 seconds
    mock_config_entry.options = {CONF_REFRESH_INTERVAL: 45}

    await _async_options_updated(hass, mock_config_entry)

    assert mock_coordinator.update_interval == timedelta(seconds=45)
    mock_coordinator.async_request_refresh.assert_called_once()
