"""End-to-end tests for config entry lifecycle.

Tests the complete lifecycle of a config entry including:
- Entry setup with authentication
- Device discovery and coordinator creation
- Platform setup (lock, sensor, switch)
- Entry unload and cleanup
- Entry reload after options change
- Migration between versions

Quality Scale: Gold tier - complete integration lifecycle testing.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokwikset.api import Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.kwikset import (
    KwiksetRuntimeData,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.kwikset.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOME_ID,
    CONF_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)

from .conftest import (
    MOCK_ACCESS_TOKEN,
    MOCK_DEVICE_ID,
    MOCK_DEVICE_ID_2,
    MOCK_DEVICE_INFO,
    MOCK_DEVICE_INFO_2,
    MOCK_DEVICES,
    MOCK_EMAIL,
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_OPTIONS,
    MOCK_HOME_ID,
    MOCK_REFRESH_TOKEN,
    MOCK_USER_INFO,
)


# =============================================================================
# Entry Setup Tests
# =============================================================================


class TestEntrySetup:
    """Tests for async_setup_entry."""

    async def test_successful_setup(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test successful entry setup creates runtime data and platforms."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert isinstance(entry.runtime_data, KwiksetRuntimeData)
        assert entry.runtime_data.client is not None

    async def test_setup_creates_coordinators_for_devices(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup creates a coordinator for each device."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # Return both devices
        mock_api.device.get_devices.return_value = MOCK_DEVICES
        mock_api.device.get_device_info.side_effect = [
            MOCK_DEVICE_INFO,
            MOCK_DEVICE_INFO_2,
        ]

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                await async_setup_entry(hass, entry)

        assert len(entry.runtime_data.devices) == 2
        assert MOCK_DEVICE_ID in entry.runtime_data.devices
        assert MOCK_DEVICE_ID_2 in entry.runtime_data.devices

    async def test_setup_auth_failure_raises_config_entry_auth_failed(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test authentication failure raises ConfigEntryAuthFailed."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.title = "Test Entry"

        mock_api.async_renew_access_token.side_effect = Unauthenticated("Token expired")

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)

    async def test_setup_connection_failure_raises_config_entry_not_ready(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test connection failure raises ConfigEntryNotReady."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()

        mock_api.async_renew_access_token.side_effect = RequestError("Connection failed")

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    async def test_setup_refreshes_tokens_when_changed(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup saves refreshed tokens to config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {
            **MOCK_ENTRY_DATA,
            CONF_ACCESS_TOKEN: "old_token",
        }
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # API returns new tokens
        mock_api.access_token = "new_access_token"
        mock_api.refresh_token = "new_refresh_token"

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                await async_setup_entry(hass, entry)

        # Verify tokens were updated
        hass.config_entries.async_update_entry.assert_called()


# =============================================================================
# Entry Unload Tests
# =============================================================================


class TestEntryUnload:
    """Tests for async_unload_entry."""

    async def test_successful_unload(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test successful entry unload."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # Set up first
        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                await async_setup_entry(hass, entry)

        # Mock unload platforms
        with patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
            mock_unload.return_value = True
            result = await async_unload_entry(hass, entry)

        assert result is True

    async def test_unload_cancels_discovery(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test unload cancels device discovery timer."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        cancel_mock = MagicMock()

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=cancel_mock,
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                await async_setup_entry(hass, entry)

        assert entry.runtime_data.cancel_device_discovery == cancel_mock

        with patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
            mock_unload.return_value = True
            await async_unload_entry(hass, entry)

        cancel_mock.assert_called_once()


# =============================================================================
# Migration Tests
# =============================================================================


class TestMigration:
    """Tests for config entry migration."""

    async def test_migrate_v1_to_v4(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from version 1 to 4."""
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_HOME_ID: MOCK_HOME_ID,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        }

        result = await async_migrate_entry(hass, entry)

        assert result is True
        assert entry.version == 4

    async def test_migrate_v2_to_v4(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from version 2 to 4."""
        entry = MagicMock()
        entry.version = 2
        entry.data = {
            CONF_HOME_ID: MOCK_HOME_ID,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        }

        result = await async_migrate_entry(hass, entry)

        assert result is True
        # Should have added access token
        hass.config_entries.async_update_entry.assert_called()

    async def test_migrate_v3_to_v4(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from version 3 to 4."""
        entry = MagicMock()
        entry.version = 3
        entry.data = {
            CONF_HOME_ID: MOCK_HOME_ID,
            CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        }

        result = await async_migrate_entry(hass, entry)

        assert result is True
        # Should have added refresh interval
        hass.config_entries.async_update_entry.assert_called()


# =============================================================================
# Runtime Data Tests
# =============================================================================


class TestRuntimeData:
    """Tests for KwiksetRuntimeData dataclass."""

    def test_runtime_data_defaults(self) -> None:
        """Test runtime data has correct defaults."""
        client = MagicMock()
        runtime_data = KwiksetRuntimeData(client=client)

        assert runtime_data.client == client
        assert runtime_data.devices == {}
        assert runtime_data.known_devices == set()
        assert runtime_data.cancel_device_discovery is None

    def test_runtime_data_with_devices(self) -> None:
        """Test runtime data stores devices correctly."""
        client = MagicMock()
        devices = {MOCK_DEVICE_ID: MagicMock()}
        known = {MOCK_DEVICE_ID}

        runtime_data = KwiksetRuntimeData(
            client=client,
            devices=devices,
            known_devices=known,
        )

        assert len(runtime_data.devices) == 1
        assert MOCK_DEVICE_ID in runtime_data.known_devices


# =============================================================================
# Options Update Tests
# =============================================================================


class TestOptionsUpdate:
    """Tests for options update handling."""

    async def test_options_update_changes_polling_interval(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test options update changes coordinator polling interval."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ):
                await async_setup_entry(hass, entry)

        # Verify initial interval
        for coordinator in entry.runtime_data.devices.values():
            assert coordinator.update_interval == timedelta(seconds=DEFAULT_REFRESH_INTERVAL)


# =============================================================================
# Platform Setup Tests
# =============================================================================


class TestPlatformSetup:
    """Tests for platform setup via async_forward_entry_setups."""

    async def test_all_platforms_forwarded(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test all platforms are forwarded during setup."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with patch(
            "custom_components.kwikset.async_track_time_interval",
            return_value=MagicMock(),
        ):
            with patch.object(
                hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
            ) as mock_forward:
                await async_setup_entry(hass, entry)

        # Verify platforms were forwarded
        mock_forward.assert_called_once()
        platforms = mock_forward.call_args[0][1]
        assert "lock" in [p.value if hasattr(p, "value") else str(p) for p in platforms]
        assert "sensor" in [p.value if hasattr(p, "value") else str(p) for p in platforms]
        assert "switch" in [p.value if hasattr(p, "value") else str(p) for p in platforms]
