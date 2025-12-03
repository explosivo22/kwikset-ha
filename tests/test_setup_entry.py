"""Tests for config entry setup and unload.

Tests the async_setup_entry and async_unload_entry functions including:
- Successful setup with token refresh
- Authentication failure handling
- Connection failure handling
- Device discovery and coordinator creation
- Platform forwarding
- Options update listener registration
- Clean unload and resource cleanup
- Discovery timer cancellation

Quality Scale: Gold tier - complete entry lifecycle testing.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from aiokwikset.api import Unauthenticated
from aiokwikset.errors import RequestError
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kwikset import PLATFORMS
from custom_components.kwikset import KwiksetRuntimeData
from custom_components.kwikset import async_migrate_entry
from custom_components.kwikset import async_setup_entry
from custom_components.kwikset import async_unload_entry
from custom_components.kwikset.const import CONF_ACCESS_TOKEN
from custom_components.kwikset.const import CONF_HOME_ID
from custom_components.kwikset.const import CONF_REFRESH_INTERVAL
from custom_components.kwikset.const import CONF_REFRESH_TOKEN
from custom_components.kwikset.const import DEFAULT_REFRESH_INTERVAL
from custom_components.kwikset.const import DOMAIN

from .conftest import MOCK_ACCESS_TOKEN
from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_DEVICE_ID_2
from .conftest import MOCK_DEVICE_INFO
from .conftest import MOCK_DEVICE_INFO_2
from .conftest import MOCK_DEVICES
from .conftest import MOCK_ENTRY_DATA
from .conftest import MOCK_ENTRY_OPTIONS
from .conftest import MOCK_HOME_ID
from .conftest import MOCK_REFRESH_TOKEN

# =============================================================================
# Setup Entry Tests
# =============================================================================


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    async def test_setup_returns_true_on_success(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup returns True on successful initialization."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True

    async def test_setup_creates_runtime_data(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup creates KwiksetRuntimeData with correct structure."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert hasattr(entry, "runtime_data")
        assert isinstance(entry.runtime_data, KwiksetRuntimeData)
        assert entry.runtime_data.client is not None
        assert isinstance(entry.runtime_data.devices, dict)
        assert isinstance(entry.runtime_data.known_devices, set)

    async def test_setup_authenticates_with_api(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup calls API authentication methods."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        # Verify session restoration with tokens
        mock_api.async_authenticate_with_tokens.assert_called_once()
        mock_api.user.get_info.assert_called_once()

    async def test_setup_fetches_devices(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup fetches devices from API."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        mock_api.device.get_devices.assert_called_once_with(MOCK_HOME_ID)

    async def test_setup_creates_coordinator_for_each_device(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup creates a coordinator for each discovered device."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # Return multiple devices
        mock_api.device.get_devices.return_value = MOCK_DEVICES

        # Return different device info for each device ID
        def get_device_info_side_effect(device_id: str) -> dict:
            if device_id == MOCK_DEVICE_ID:
                return MOCK_DEVICE_INFO
            if device_id == MOCK_DEVICE_ID_2:
                return MOCK_DEVICE_INFO_2
            raise ValueError(f"Unknown device ID: {device_id}")

        mock_api.device.get_device_info = AsyncMock(
            side_effect=get_device_info_side_effect
        )

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert len(entry.runtime_data.devices) == 2
        assert MOCK_DEVICE_ID in entry.runtime_data.devices
        assert MOCK_DEVICE_ID_2 in entry.runtime_data.devices
        assert len(entry.runtime_data.known_devices) == 2

    async def test_setup_forwards_platforms(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup forwards all platforms."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ) as mock_forward,
        ):
            await async_setup_entry(hass, entry)

        mock_forward.assert_called_once()
        call_args = mock_forward.call_args
        assert call_args[0][0] == entry
        # Check all platforms are forwarded
        forwarded_platforms = call_args[0][1]
        assert Platform.LOCK in forwarded_platforms
        assert Platform.SENSOR in forwarded_platforms
        assert Platform.SWITCH in forwarded_platforms

    async def test_setup_registers_options_listener(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup registers options update listener."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        # Should register listener via async_on_unload
        entry.async_on_unload.assert_called()

    async def test_setup_starts_device_discovery_timer(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup starts periodic device discovery timer."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        cancel_mock = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=cancel_mock,
            ) as mock_track,
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        mock_track.assert_called_once()
        assert entry.runtime_data.cancel_device_discovery == cancel_mock


# =============================================================================
# Setup Error Handling Tests
# =============================================================================


class TestSetupErrorHandling:
    """Tests for error handling during setup."""

    async def test_setup_raises_auth_failed_on_unauthenticated(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup raises ConfigEntryAuthFailed on authentication failure."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.title = "Test Entry"

        mock_api.async_authenticate_with_tokens.side_effect = Unauthenticated(
            "Token expired"
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)

    async def test_setup_raises_not_ready_on_request_error(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test setup raises ConfigEntryNotReady on connection failure."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()

        mock_api.async_authenticate_with_tokens.side_effect = RequestError(
            "Connection failed"
        )

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    async def test_setup_updates_tokens_when_refreshed(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test token callback updates config entry when tokens are refreshed."""
        # Use MockConfigEntry with add_to_hass to enable async_update_entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="test_entry_id",
            data={
                **MOCK_ENTRY_DATA,
                CONF_ACCESS_TOKEN: "old_access_token",
            },
            options=MOCK_ENTRY_OPTIONS.copy(),
            version=5,
        )
        entry.add_to_hass(hass)

        # Capture the token_update_callback that will be passed to API
        captured_callback = None

        def capture_callback(*args, **kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("token_update_callback")
            return mock_api

        with patch(
            "custom_components.kwikset.API",
            side_effect=capture_callback,
        ):
            with patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ):
                with patch.object(
                    hass.config_entries,
                    "async_forward_entry_setups",
                    new_callable=AsyncMock,
                ):
                    await async_setup_entry(hass, entry)

        # Verify callback was registered
        assert captured_callback is not None

        # Simulate token refresh via callback
        await captured_callback("new_id_token", "new_access_token", "new_refresh_token")

        # Verify tokens were updated via callback
        assert entry.data.get(CONF_ACCESS_TOKEN) == "new_access_token"
        assert entry.data.get(CONF_REFRESH_TOKEN) == "new_refresh_token"


# =============================================================================
# Unload Entry Tests
# =============================================================================


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry function."""

    async def test_unload_returns_true_on_success(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test unload returns True on successful cleanup."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # Set up first
        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        # Unload
        with patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
            mock_unload.return_value = True
            result = await async_unload_entry(hass, entry)

        assert result is True

    async def test_unload_cancels_discovery_timer(
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

        # Set up with discovery timer
        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=cancel_mock,
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        # Verify timer is registered
        assert entry.runtime_data.cancel_device_discovery is not None

        # Unload
        with patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
            mock_unload.return_value = True
            await async_unload_entry(hass, entry)

        # Verify timer was cancelled
        cancel_mock.assert_called_once()
        assert entry.runtime_data.cancel_device_discovery is None

    async def test_unload_unloads_all_platforms(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test unload unloads all platforms."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = MOCK_ENTRY_OPTIONS.copy()
        entry.async_on_unload = MagicMock()

        # Set up first
        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        # Unload
        with patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload:
            mock_unload.return_value = True
            await async_unload_entry(hass, entry)

        mock_unload.assert_called_once_with(entry, PLATFORMS)


# =============================================================================
# Migration Tests
# =============================================================================


class TestAsyncMigrateEntry:
    """Tests for async_migrate_entry function."""

    async def test_migrate_from_v1_to_v5(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from version 1 to current version.

        Note: This test uses MagicMock because the source code's v1 migration
        directly sets config_entry.version, which isn't allowed for real
        ConfigEntry objects in modern Home Assistant.
        """
        # Use MagicMock for v1 migration because source code directly sets version
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_HOME_ID: MOCK_HOME_ID,
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
        }
        entry.entry_id = "mock_entry_id"

        # Create a mock that actually updates the entry version
        def update_entry_side_effect(config_entry, **kwargs):
            if "version" in kwargs:
                config_entry.version = kwargs["version"]
            if "data" in kwargs:
                config_entry.data = kwargs["data"]

        # Mock async_update_entry since MagicMock isn't a real entry
        with patch.object(
            hass.config_entries,
            "async_update_entry",
            side_effect=update_entry_side_effect,
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True
        assert entry.version == 5

    async def test_migrate_from_v2_adds_access_token(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from v2 adds access token."""
        # Use MockConfigEntry for proper registration
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="test_entry_id",
            version=2,
            data={
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        assert result is True
        # Verify access token was added
        assert CONF_ACCESS_TOKEN in entry.data

    async def test_migrate_from_v3_adds_refresh_interval(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration from v3 adds refresh interval."""
        # Use MockConfigEntry for proper registration
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="test_entry_id",
            version=3,
            data={
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
                CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        assert result is True
        # Verify refresh interval was added
        assert CONF_REFRESH_INTERVAL in entry.data

    async def test_migrate_returns_true_for_current_version(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test migration returns True for already current version."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="test_entry_id",
            version=5,
            data=MOCK_ENTRY_DATA.copy(),
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        assert result is True


# =============================================================================
# Runtime Data Tests
# =============================================================================


class TestKwiksetRuntimeData:
    """Tests for KwiksetRuntimeData dataclass."""

    def test_runtime_data_has_required_fields(self) -> None:
        """Test runtime data has all required fields."""
        client = MagicMock()
        runtime_data = KwiksetRuntimeData(client=client)

        assert hasattr(runtime_data, "client")
        assert hasattr(runtime_data, "devices")
        assert hasattr(runtime_data, "known_devices")
        assert hasattr(runtime_data, "cancel_device_discovery")

    def test_runtime_data_defaults(self) -> None:
        """Test runtime data has correct default values."""
        client = MagicMock()
        runtime_data = KwiksetRuntimeData(client=client)

        assert runtime_data.client == client
        assert runtime_data.devices == {}
        assert runtime_data.known_devices == set()
        assert runtime_data.cancel_device_discovery is None

    def test_runtime_data_with_values(self) -> None:
        """Test runtime data stores values correctly."""
        client = MagicMock()
        devices = {MOCK_DEVICE_ID: MagicMock()}
        known = {MOCK_DEVICE_ID}
        cancel = MagicMock()

        runtime_data = KwiksetRuntimeData(
            client=client,
            devices=devices,
            known_devices=known,
            cancel_device_discovery=cancel,
        )

        assert runtime_data.client == client
        assert len(runtime_data.devices) == 1
        assert MOCK_DEVICE_ID in runtime_data.known_devices
        assert runtime_data.cancel_device_discovery == cancel


# =============================================================================
# Platforms Constant Tests
# =============================================================================


class TestPlatformsConstant:
    """Tests for PLATFORMS constant."""

    def test_platforms_contains_lock(self) -> None:
        """Test PLATFORMS includes lock platform."""
        assert Platform.LOCK in PLATFORMS

    def test_platforms_contains_sensor(self) -> None:
        """Test PLATFORMS includes sensor platform."""
        assert Platform.SENSOR in PLATFORMS

    def test_platforms_contains_switch(self) -> None:
        """Test PLATFORMS includes switch platform."""
        assert Platform.SWITCH in PLATFORMS

    def test_platforms_count(self) -> None:
        """Test PLATFORMS has exactly 3 platforms."""
        assert len(PLATFORMS) == 3


# =============================================================================
# Coordinator Interval Tests
# =============================================================================


class TestCoordinatorInterval:
    """Tests for coordinator update interval configuration."""

    async def test_coordinator_uses_default_interval(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test coordinators use default refresh interval."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = {}  # No custom interval
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        for coordinator in entry.runtime_data.devices.values():
            assert coordinator.update_interval == timedelta(
                seconds=DEFAULT_REFRESH_INTERVAL
            )

    async def test_coordinator_uses_custom_interval(
        self,
        hass: HomeAssistant,
        mock_api: MagicMock,
    ) -> None:
        """Test coordinators use custom refresh interval from options."""
        custom_interval = 45
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = MOCK_ENTRY_DATA.copy()
        entry.options = {CONF_REFRESH_INTERVAL: custom_interval}
        entry.async_on_unload = MagicMock()

        with (
            patch(
                "custom_components.kwikset.async_track_time_interval",
                return_value=MagicMock(),
            ),
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new_callable=AsyncMock,
            ),
        ):
            await async_setup_entry(hass, entry)

        for coordinator in entry.runtime_data.devices.values():
            assert coordinator.update_interval == timedelta(seconds=custom_interval)
