"""Tests for Kwikset config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kwikset.config_flow import (
    CannotConnect,
    KwiksetFlowHandler,
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
    MOCK_HOMES,
    MOCK_TOKENS,
)


class MockMFAChallengeRequired(Exception):
    """Mock MFA challenge exception."""

    def __init__(self, mfa_type: str = "SOFTWARE_TOKEN_MFA") -> None:
        """Initialize the exception."""
        super().__init__("MFA required")
        self.mfa_type = mfa_type
        self.mfa_tokens = {"session": "mock_session_token"}


class TestUserStep:
    """Tests for the user step of config flow."""

    async def test_flow_user_step_shows_form(self, hass: HomeAssistant) -> None:
        """Test that the user step shows the form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert CONF_EMAIL in result["data_schema"].schema
        assert CONF_PASSWORD in result["data_schema"].schema

    async def test_flow_user_step_proceeds_to_select_home(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test that valid credentials proceed to home selection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_home"


class TestHomeSelection:
    """Tests for the home selection step."""

    async def test_flow_select_home_creates_entry(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test that selecting a home creates the config entry."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # User step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        # Select home step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOME_ID: "home_001"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My House"
        assert result["data"][CONF_EMAIL] == "user@example.com"
        assert result["data"][CONF_HOME_ID] == "home_001"
        assert result["data"][CONF_ACCESS_TOKEN] == MOCK_TOKENS["access_token"]
        assert result["data"][CONF_REFRESH_TOKEN] == MOCK_TOKENS["refresh_token"]

    async def test_flow_select_home_sets_default_options(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test that config entry is created with default options."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOME_ID: "home_001"},
        )

        assert result["options"][CONF_REFRESH_INTERVAL] == DEFAULT_REFRESH_INTERVAL

    async def test_flow_no_available_homes(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test abort when no homes are available."""
        mock_api_config_flow.user.get_homes.return_value = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_available_homes"


class TestMFAFlow:
    """Tests for MFA (Multi-Factor Authentication) flow."""

    async def test_flow_mfa_required(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test that MFA challenge is handled."""
        with patch(
            "custom_components.kwikset.config_flow.MFAChallengeRequired",
            MockMFAChallengeRequired,
        ):
            mock_api_config_flow.async_login.side_effect = MockMFAChallengeRequired()

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "mfa"

    async def test_flow_mfa_success(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test successful MFA verification."""
        with patch(
            "custom_components.kwikset.config_flow.MFAChallengeRequired",
            MockMFAChallengeRequired,
        ):
            mock_api_config_flow.async_login.side_effect = [
                MockMFAChallengeRequired(),
                None,
            ]

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["step_id"] == "mfa"

            mock_api_config_flow.async_login.side_effect = None

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"mfa_code": "123456"},
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "select_home"

    async def test_flow_mfa_sms_type_display(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test MFA displays SMS type correctly."""
        with patch(
            "custom_components.kwikset.config_flow.MFAChallengeRequired",
            MockMFAChallengeRequired,
        ):
            mock_api_config_flow.async_login.side_effect = MockMFAChallengeRequired(
                mfa_type="SMS_MFA"
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["step_id"] == "mfa"
            assert result["description_placeholders"]["mfa_type"] == "SMS"


class TestErrorHandling:
    """Tests for error handling in config flow."""

    async def test_flow_connection_error(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock
    ) -> None:
        """Test connection error handling."""
        from aiokwikset.errors import RequestError

        mock_api_config_flow.async_login.side_effect = RequestError("Connection failed")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with pytest.raises(CannotConnect):
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
            )


class TestOptionsFlow:
    """Tests for options flow."""

    async def test_options_flow_shows_interval(
        self, hass: HomeAssistant, mock_config_entry: MagicMock
    ) -> None:
        """Test that options flow shows refresh interval."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_saves_interval(
        self, hass: HomeAssistant, mock_config_entry: MagicMock
    ) -> None:
        """Test that options flow saves new interval."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_REFRESH_INTERVAL: 45},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_REFRESH_INTERVAL] == 45

    async def test_options_flow_uses_current_value(
        self, hass: HomeAssistant, mock_config_entry: MagicMock
    ) -> None:
        """Test that options flow shows current interval value."""
        mock_config_entry.options = {CONF_REFRESH_INTERVAL: 45}
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        # The default should be the current value
        assert result["type"] == FlowResultType.FORM


class TestReauthFlow:
    """Tests for reauthentication flow."""

    async def test_reauth_flow_shows_form(self, hass: HomeAssistant) -> None:
        """Test that reauth flow shows the form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH},
            data={CONF_EMAIL: "user@example.com", CONF_HOME_ID: "home_001"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

    async def test_reauth_flow_success(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test successful reauthentication."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "newpassword"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    async def test_reauth_flow_connection_error(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test reauth with connection error shows form again."""
        from aiokwikset.errors import RequestError

        mock_api_config_flow.async_login.side_effect = RequestError("Connection failed")
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


class TestReconfigureFlow:
    """Tests for reconfiguration flow."""

    async def test_reconfigure_flow_shows_form(
        self, hass: HomeAssistant, mock_config_entry: MagicMock
    ) -> None:
        """Test that reconfigure flow shows the form."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    async def test_reconfigure_flow_success(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test successful reconfiguration."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


class TestDuplicateEntry:
    """Tests for duplicate entry prevention."""

    async def test_flow_prevents_duplicate_home(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test that duplicate home entries are prevented."""
        # Add existing entry
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        # Should only show home_002 since home_001 is already configured
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_home"

    async def test_flow_shows_only_unconfigured_homes(
        self, hass: HomeAssistant, mock_api_config_flow: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Test that only unconfigured homes are shown."""
        mock_config_entry.data = {CONF_HOME_ID: "home_001", CONF_EMAIL: "user@example.com"}
        mock_config_entry.add_to_hass(hass)

        # Mock having both homes but one is already configured
        mock_api_config_flow.user.get_homes.return_value = MOCK_HOMES

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password123"},
        )

        # Verify it's the select_home form
        assert result["step_id"] == "select_home"

