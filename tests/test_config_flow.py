"""Tests for Kwikset config flow.

Tests the complete config flow including:
- Initial user setup flow
- Home selection step
- MFA challenge handling
- Reauthentication flow
- Reconfigure flow
- Options flow
- Error handling

Quality Scale: Gold tier - comprehensive config flow test coverage.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokwikset.errors import MFAChallengeRequired, RequestError

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    MOCK_ACCESS_TOKEN,
    MOCK_EMAIL,
    MOCK_HOME_ID,
    MOCK_HOME_NAME,
    MOCK_HOMES,
    MOCK_PASSWORD,
    MOCK_REFRESH_TOKEN,
)


# =============================================================================
# User Flow Tests
# =============================================================================


class TestUserFlow:
    """Tests for the initial user setup flow."""

    async def test_show_user_form(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test that user form is shown on init."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_user_flow_success(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test successful user flow with home selection."""
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Submit credentials
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        # Should show home selection
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_home"

    async def test_user_flow_cannot_connect(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test user flow with connection error."""
        mock_api_config_flow.async_login.side_effect = RequestError("Connection failed")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        # Should abort due to connection error in select_home step
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"

    async def test_user_flow_unknown_error(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test user flow with unexpected error."""
        mock_api_config_flow.async_login.side_effect = Exception("Unexpected error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unknown"


# =============================================================================
# Home Selection Tests
# =============================================================================


class TestHomeSelection:
    """Tests for the home selection step."""

    async def test_select_home_creates_entry(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test selecting a home creates a config entry."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        # Select home
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOME_ID: MOCK_HOME_ID},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == MOCK_HOME_NAME
        assert result["data"][CONF_EMAIL] == MOCK_EMAIL
        assert result["data"][CONF_HOME_ID] == MOCK_HOME_ID
        assert result["data"][CONF_ACCESS_TOKEN] == MOCK_ACCESS_TOKEN
        assert result["data"][CONF_REFRESH_TOKEN] == MOCK_REFRESH_TOKEN
        assert result["options"][CONF_REFRESH_INTERVAL] == DEFAULT_REFRESH_INTERVAL

    async def test_no_available_homes_aborts(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test that flow aborts when all homes are already configured."""
        # Create existing entry for all homes
        mock_api_config_flow.user.get_homes.return_value = [
            {"homeid": MOCK_HOME_ID, "homename": MOCK_HOME_NAME}
        ]

        # Create an existing entry
        existing_entry = MagicMock()
        existing_entry.data = {CONF_HOME_ID: MOCK_HOME_ID}

        with patch.object(
            KwiksetFlowHandler,
            "_async_current_entries",
            return_value=[existing_entry],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
            )

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "no_available_homes"


# =============================================================================
# MFA Flow Tests
# =============================================================================


class TestMFAFlow:
    """Tests for multi-factor authentication flow."""

    async def test_mfa_challenge_required(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test MFA challenge is handled correctly."""
        mock_api_config_flow.async_login.side_effect = MFAChallengeRequired(
            mfa_type="SOFTWARE_TOKEN_MFA",
            mfa_tokens={"session": "mock_session"},
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"

    async def test_mfa_success(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test successful MFA verification."""
        # First call triggers MFA, subsequent calls succeed
        mock_api_config_flow.async_login.side_effect = [
            MFAChallengeRequired(
                mfa_type="SOFTWARE_TOKEN_MFA",
                mfa_tokens={"session": "mock_session"},
            ),
            None,  # Second call succeeds after MFA
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        # Submit MFA code
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"mfa_code": "123456"},
        )

        # Should proceed to home selection
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_home"

    async def test_mfa_invalid_code(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test invalid MFA code shows error."""
        mock_api_config_flow.async_login.side_effect = MFAChallengeRequired(
            mfa_type="SMS_MFA",
            mfa_tokens={"session": "mock_session"},
        )
        mock_api_config_flow.async_respond_to_mfa_challenge.side_effect = RequestError(
            "Invalid MFA code"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"mfa_code": "wrong_code"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_mfa"


# =============================================================================
# Reauthentication Flow Tests
# =============================================================================


class TestReauthFlow:
    """Tests for reauthentication flow."""

    async def test_reauth_flow_shows_form(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test reauthentication shows the confirm form."""
        # Create a mock config entry for reauth
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: MOCK_EMAIL,
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: "old_token",
                CONF_REFRESH_TOKEN: "old_refresh",
            },
            title="Test Home",
            unique_id=MOCK_HOME_ID,
            version=4,
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

    async def test_reauth_with_mfa(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test reauthentication with MFA challenge."""
        mock_api_config_flow.async_login.side_effect = MFAChallengeRequired(
            mfa_type="SOFTWARE_TOKEN_MFA",
            mfa_tokens={"session": "mock_session"},
        )

        # Create a mock config entry for reauth
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: MOCK_EMAIL,
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: "old_token",
                CONF_REFRESH_TOKEN: "old_refresh",
            },
            title="Test Home",
            unique_id=MOCK_HOME_ID,
            version=4,
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa_reauth"


# =============================================================================
# Reconfigure Flow Tests
# =============================================================================


class TestReconfigureFlow:
    """Tests for reconfigure flow."""

    async def test_reconfigure_form_shown(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test reconfigure form is displayed."""
        # Create a mock config entry for reconfigure
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: MOCK_EMAIL,
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
                CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            },
            title="Test Home",
            unique_id=MOCK_HOME_ID,
            version=4,
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"


# =============================================================================
# Options Flow Tests
# =============================================================================


class TestOptionsFlow:
    """Tests for options flow."""

    async def test_options_flow_init(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test options flow initialization."""
        # Create a mock config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: MOCK_EMAIL,
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
                CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            },
            options={CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL},
            title="Test Home",
            unique_id=MOCK_HOME_ID,
            version=4,
        )
        entry.add_to_hass(hass)

        # Initialize options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_saves_interval(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test options flow saves new refresh interval."""
        # Create a mock config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: MOCK_EMAIL,
                CONF_HOME_ID: MOCK_HOME_ID,
                CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
                CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            },
            options={CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL},
            title="Test Home",
            unique_id=MOCK_HOME_ID,
            version=4,
        )
        entry.add_to_hass(hass)

        # Initialize and complete options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_REFRESH_INTERVAL: 45},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_REFRESH_INTERVAL] == 45


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_duplicate_entry_prevented(
        self,
        hass: HomeAssistant,
        mock_api_config_flow: MagicMock,
    ) -> None:
        """Test that duplicate entries are prevented via unique_id."""
        # Complete first flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOME_ID: MOCK_HOME_ID},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        # Try to create another entry for the same home
        mock_api_config_flow.user.get_homes.return_value = [
            {"homeid": "home_002", "homename": "Vacation Home"}
        ]

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

        # Should show vacation home since home_001 is already configured
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "select_home"

    def test_cannot_connect_exception(self) -> None:
        """Test CannotConnect exception is a HomeAssistantError."""
        from homeassistant import exceptions

        assert issubclass(CannotConnect, exceptions.HomeAssistantError)

    async def test_flow_handler_version(self) -> None:
        """Test flow handler has correct version."""
        assert KwiksetFlowHandler.VERSION == 4
