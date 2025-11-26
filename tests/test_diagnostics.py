"""Tests for Kwikset diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant

from custom_components.kwikset import KwiksetRuntimeData
from custom_components.kwikset.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_DEVICE_NAME,
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_OPTIONS,
)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator for diagnostics testing."""
    coordinator = MagicMock()
    coordinator.device_id = MOCK_DEVICE_ID
    coordinator.device_name = MOCK_DEVICE_NAME
    coordinator.model = "Halo Touch"
    coordinator.firmware_version = "1.2.3"
    coordinator.status = "Locked"
    coordinator.battery_percentage = 85
    coordinator.led_status = True
    coordinator.audio_status = True
    coordinator.secure_screen_status = False
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
def mock_config_entry_with_runtime(mock_coordinator: MagicMock) -> MagicMock:
    """Create a mock config entry with runtime data."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.title = "My House"
    entry.version = 4
    entry.data = MOCK_ENTRY_DATA.copy()
    entry.options = MOCK_ENTRY_OPTIONS.copy()
    entry.runtime_data = KwiksetRuntimeData(
        client=MagicMock(),
        devices={MOCK_DEVICE_ID: mock_coordinator},
        known_devices={MOCK_DEVICE_ID},
    )
    return entry


class TestDiagnostics:
    """Tests for diagnostics functionality."""

    async def test_diagnostics_returns_entry_data(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics includes entry information."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert "entry" in result
        assert result["entry"]["title"] == "My House"
        assert result["entry"]["version"] == 4

    async def test_diagnostics_returns_device_count(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics includes device count."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert result["device_count"] == 1

    async def test_diagnostics_returns_devices_list(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics includes devices list."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert "devices" in result
        assert len(result["devices"]) == 1

    async def test_diagnostics_device_info_complete(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics device info is complete."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        device = result["devices"][0]
        assert "device_name" in device
        assert "model" in device
        assert "firmware_version" in device
        assert "status" in device
        assert "battery_percentage" in device
        assert "led_status" in device
        assert "audio_status" in device
        assert "secure_screen_status" in device
        assert "last_update_success" in device

    async def test_diagnostics_redacts_entry_data(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics redacts sensitive entry data."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        entry_data = result["entry"]["data"]
        # Access tokens should be redacted
        assert entry_data.get("conf_access_token") == "**REDACTED**"
        assert entry_data.get("conf_refresh_token") == "**REDACTED**"

    async def test_diagnostics_includes_options(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics includes options."""
        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert "options" in result["entry"]
        assert result["entry"]["options"] == MOCK_ENTRY_OPTIONS

    async def test_diagnostics_empty_devices(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics handles empty devices dict."""
        mock_config_entry_with_runtime.runtime_data.devices = {}

        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert result["devices"] == []
        assert result["device_count"] == 0

    async def test_diagnostics_multiple_devices(
        self, hass: HomeAssistant, mock_config_entry_with_runtime: MagicMock
    ) -> None:
        """Test diagnostics handles multiple devices."""
        # Add a second device
        second_coordinator = MagicMock()
        second_coordinator.device_id = "device_456"
        second_coordinator.device_name = "Back Door Lock"
        second_coordinator.model = "Halo Wi-Fi"
        second_coordinator.firmware_version = "2.0.0"
        second_coordinator.status = "Unlocked"
        second_coordinator.battery_percentage = 50
        second_coordinator.led_status = False
        second_coordinator.audio_status = False
        second_coordinator.secure_screen_status = True
        second_coordinator.last_update_success = True

        mock_config_entry_with_runtime.runtime_data.devices["device_456"] = (
            second_coordinator
        )

        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry_with_runtime
        )

        assert result["device_count"] == 2
        assert len(result["devices"]) == 2


class TestRedactionKeys:
    """Tests for redaction key configuration."""

    def test_redact_keys_include_email(self) -> None:
        """Test email is in redaction keys."""
        from homeassistant.const import CONF_EMAIL

        assert CONF_EMAIL in TO_REDACT

    def test_redact_keys_include_password(self) -> None:
        """Test password is in redaction keys."""
        from homeassistant.const import CONF_PASSWORD

        assert CONF_PASSWORD in TO_REDACT

    def test_redact_keys_include_tokens(self) -> None:
        """Test tokens are in redaction keys."""
        from custom_components.kwikset.const import (
            CONF_ACCESS_TOKEN,
            CONF_REFRESH_TOKEN,
        )

        assert CONF_ACCESS_TOKEN in TO_REDACT
        assert CONF_REFRESH_TOKEN in TO_REDACT

    def test_redact_keys_include_home_id(self) -> None:
        """Test home_id is in redaction keys."""
        from custom_components.kwikset.const import CONF_HOME_ID

        assert CONF_HOME_ID in TO_REDACT

    def test_redact_keys_include_device_identifiers(self) -> None:
        """Test device identifiers are in redaction keys."""
        assert "deviceid" in TO_REDACT
        assert "serialnumber" in TO_REDACT

    def test_redact_keys_include_user_identifiers(self) -> None:
        """Test user identifiers are in redaction keys."""
        assert "userid" in TO_REDACT
        assert "email" in TO_REDACT
        assert "firstname" in TO_REDACT
        assert "lastname" in TO_REDACT
