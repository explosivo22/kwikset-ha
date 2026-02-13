"""Tests for Kwikset diagnostics.

Tests the diagnostic data collection and sensitive data redaction.

Quality Scale: Gold tier - diagnostics test coverage.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.kwikset.diagnostics import async_get_config_entry_diagnostics

from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_DEVICE_NAME

# =============================================================================
# Diagnostics Tests
# =============================================================================


class TestDiagnostics:
    """Tests for async_get_config_entry_diagnostics."""

    async def test_diagnostics_returns_expected_structure(
        self,
        hass: HomeAssistant,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test diagnostics returns data with expected top-level keys."""
        entry = MagicMock()
        entry.title = "Test Home"
        entry.version = 5
        entry.data = {
            "email": "user@example.com",
            "conf_home_id": "home_001",
            "conf_id_token": "secret_id_token",
            "conf_access_token": "secret_access_token",
            "conf_refresh_token": "secret_refresh_token",
        }
        entry.options = {"refresh_interval": 30}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {MOCK_DEVICE_ID: mock_coordinator}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "entry" in result
        assert "devices" in result
        assert "device_count" in result
        assert result["device_count"] == 1
        assert result["entry"]["title"] == "Test Home"
        assert result["entry"]["version"] == 5
        assert result["entry"]["options"] == {"refresh_interval": 30}

    async def test_diagnostics_redacts_sensitive_data(
        self,
        hass: HomeAssistant,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test diagnostics redacts tokens, IDs, and PII from output."""
        entry = MagicMock()
        entry.title = "Test Home"
        entry.version = 5
        entry.data = {
            "email": "user@example.com",
            "conf_home_id": "home_001",
            "conf_id_token": "secret_id_token",
            "conf_access_token": "secret_access_token",
            "conf_refresh_token": "secret_refresh_token",
        }
        entry.options = {"refresh_interval": 30}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {MOCK_DEVICE_ID: mock_coordinator}

        result = await async_get_config_entry_diagnostics(hass, entry)

        # Verify sensitive config data is redacted
        entry_data = result["entry"]["data"]
        assert entry_data.get("email") == "**REDACTED**"
        assert entry_data.get("conf_id_token") == "**REDACTED**"
        assert entry_data.get("conf_access_token") == "**REDACTED**"
        assert entry_data.get("conf_refresh_token") == "**REDACTED**"
        assert entry_data.get("conf_home_id") == "**REDACTED**"

    async def test_diagnostics_includes_device_data(
        self,
        hass: HomeAssistant,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test diagnostics includes device information."""
        entry = MagicMock()
        entry.title = "Test Home"
        entry.version = 5
        entry.data = {}
        entry.options = {}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {MOCK_DEVICE_ID: mock_coordinator}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert len(result["devices"]) == 1
        device = result["devices"][0]
        assert device["device_name"] == MOCK_DEVICE_NAME
        assert device["model"] == "Halo Touch"
        assert device["firmware_version"] == "1.2.3"
        assert device["battery_percentage"] == 85
        assert device["led_status"] is True
        assert device["audio_status"] is True
        assert device["secure_screen_status"] is False
        assert device["last_update_success"] is True

    async def test_diagnostics_handles_empty_devices(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test diagnostics handles case with no devices."""
        entry = MagicMock()
        entry.title = "Empty Home"
        entry.version = 5
        entry.data = {}
        entry.options = {}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {}

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["device_count"] == 0
        assert result["devices"] == []

    async def test_diagnostics_multiple_devices(
        self,
        hass: HomeAssistant,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test diagnostics with multiple devices."""
        coordinator2 = MagicMock()
        coordinator2.device_name = "Back Door Lock"
        coordinator2.model = "Halo WiFi"
        coordinator2.firmware_version = "2.0.1"
        coordinator2.status = "Unlocked"
        coordinator2.battery_percentage = 72
        coordinator2.led_status = False
        coordinator2.audio_status = False
        coordinator2.secure_screen_status = True
        coordinator2.last_update_success = True

        entry = MagicMock()
        entry.title = "Test Home"
        entry.version = 5
        entry.data = {}
        entry.options = {}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {
            MOCK_DEVICE_ID: mock_coordinator,
            "device_456": coordinator2,
        }

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["device_count"] == 2
        assert len(result["devices"]) == 2

    async def test_diagnostics_redacts_stored_password(
        self,
        hass: HomeAssistant,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test diagnostics redacts stored_password from output."""
        entry = MagicMock()
        entry.title = "Test Home"
        entry.version = 6
        entry.data = {
            "email": "user@example.com",
            "conf_home_id": "home_001",
            "conf_id_token": "secret_id_token",
            "conf_access_token": "secret_access_token",
            "conf_refresh_token": "secret_refresh_token",
            "stored_password": "my_secret_password",
        }
        entry.options = {"refresh_interval": 30}
        entry.runtime_data = MagicMock()
        entry.runtime_data.devices = {MOCK_DEVICE_ID: mock_coordinator}

        result = await async_get_config_entry_diagnostics(hass, entry)

        entry_data = result["entry"]["data"]
        assert entry_data.get("stored_password") == "**REDACTED**"
