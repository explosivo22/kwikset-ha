"""Config flow for Kwikset Smart Locks integration.

This module implements the configuration flow for setting up Kwikset smart locks
in Home Assistant. It follows the Home Assistant config flow patterns:

Flow Steps:
    - user: Collect credentials (email/password)
    - select_home: Choose which Kwikset home to configure
    - mfa: Handle multi-factor authentication challenges
    - reauth_confirm: Allow re-entering credentials when tokens expire
    - reconfigure: Trigger device discovery without full re-setup
    - options: Configure polling interval

Architecture:
    - Uses aiokwikset library for all API communication
    - Tokens are stored in config_entry.data for persistence
    - Refresh interval is stored in config_entry.options for user customization
    - Each home is a separate config entry (unique_id = home_id)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiokwikset import API
from aiokwikset.errors import MFAChallengeRequired, RequestError
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_HOME_ID,
    CONF_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
    LOGGER,
)

# Schema definitions
CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

MFA_SCHEMA = vol.Schema({vol.Required("mfa_code"): str})


class KwiksetFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of Kwikset integrations.

    Manages the complete setup process:
        1. Credential collection (email/password)
        2. API authentication (with MFA support)
        3. Home selection (one entry per Kwikset home)
        4. Token storage for persistent authentication

    Also handles reauthentication when tokens expire.
    """

    VERSION = 4

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self.api: API | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.home_id: str | None = None
        self.mfa_type: str | None = None
        self.mfa_tokens: dict[str, Any] | None = None

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _get_mfa_type_display(self) -> str:
        """Get human-readable MFA type for display."""
        return "authenticator app" if self.mfa_type == "SOFTWARE_TOKEN_MFA" else "SMS"

    async def _async_authenticate(self) -> str | None:
        """Authenticate with the API.

        Returns:
            str: Error key if authentication failed
            None: On success (including when MFA is required)
        """
        try:
            self.api = API()
            await self.api.async_login(self.username, self.password)
            return None  # Success
        except MFAChallengeRequired as mfa_error:
            LOGGER.debug("MFA challenge required: %s", mfa_error.mfa_type)
            self.mfa_type = mfa_error.mfa_type
            self.mfa_tokens = mfa_error.mfa_tokens
            return None  # MFA needed, but not an error
        except RequestError as err:
            LOGGER.error("API connection error: %s", err)
            return "cannot_connect"
        except Exception:
            LOGGER.exception("Unexpected authentication error")
            return "unknown"

    async def _async_complete_mfa(self, mfa_code: str) -> str | None:
        """Complete MFA verification. Returns error key or None on success."""
        try:
            await self.api.async_respond_to_mfa_challenge(
                mfa_code=mfa_code,
                mfa_type=self.mfa_type,
                mfa_tokens=self.mfa_tokens,
            )
            LOGGER.debug("MFA authentication successful")
            return None  # Success
        except RequestError:
            LOGGER.error("MFA verification failed")
            return "invalid_mfa"
        except Exception:
            LOGGER.exception("Unexpected MFA error")
            return "unknown"

    def _create_token_data(self) -> dict[str, Any]:
        """Create token data dict for config entry."""
        return {
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

    # -------------------------------------------------------------------------
    # Reauth flow
    # -------------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication trigger."""
        self.username = entry_data.get(CONF_EMAIL)
        self.home_id = entry_data.get(CONF_HOME_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.username = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]

            error = await self._async_authenticate()
            if error:
                errors["base"] = error
            elif self.mfa_type:
                return await self.async_step_mfa_reauth()
            else:
                # Clear any auth expired issue since reauth was successful
                reauth_entry = self._get_reauth_entry()
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"auth_expired_{reauth_entry.entry_id}"
                )
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=self._create_token_data(),
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self.username or ""): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_mfa_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA during reauthentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_complete_mfa(user_input["mfa_code"])
            if error:
                errors["base"] = error
            else:
                # Clear any auth expired issue since reauth was successful
                reauth_entry = self._get_reauth_entry()
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"auth_expired_{reauth_entry.entry_id}"
                )
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=self._create_token_data(),
                )

        return self.async_show_form(
            step_id="mfa_reauth",
            data_schema=MFA_SCHEMA,
            description_placeholders={"mfa_type": self._get_mfa_type_display()},
            errors=errors,
        )

    # -------------------------------------------------------------------------
    # Reconfigure flow
    # -------------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to discover new devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reconfigure_entry()
            try:
                self.api = API()
                await self.api.async_renew_access_token(
                    entry.data[CONF_ACCESS_TOKEN],
                    entry.data[CONF_REFRESH_TOKEN],
                )
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: self.api.access_token,
                        CONF_REFRESH_TOKEN: self.api.refresh_token,
                    },
                )
            except RequestError as err:
                LOGGER.error("Reconfigure connection error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected reconfigure error")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "info": "This will reload the integration and discover any new devices."
            },
            errors=errors,
        )

    # -------------------------------------------------------------------------
    # Initial setup flow
    # -------------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial user credentials."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=CREDENTIALS_SCHEMA,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]
        return await self.async_step_select_home()

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle home selection."""
        errors: dict[str, str] = {}

        if user_input is None or CONF_HOME_ID not in user_input:
            error = await self._async_authenticate()
            if error:
                errors["base"] = error
                raise CannotConnect
            if self.mfa_type:
                return await self.async_step_mfa()

            # Get available homes (excluding already configured ones)
            existing_homes = [
                entry.data[CONF_HOME_ID] for entry in self._async_current_entries()
            ]
            homes = await self.api.user.get_homes()
            homes_options = {
                home["homeid"]: home["homename"]
                for home in homes
                if home["homeid"] not in existing_homes
            }

            if not homes_options:
                return self.async_abort(reason="no_available_homes")

            return self.async_show_form(
                step_id="select_home",
                data_schema=vol.Schema(
                    {vol.Required(CONF_HOME_ID): vol.In(homes_options)}
                ),
            )

        self.home_id = user_input[CONF_HOME_ID]
        await self.async_set_unique_id(str(self.home_id))
        self._abort_if_unique_id_configured()
        return await self.async_step_install()

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA verification during initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_complete_mfa(user_input["mfa_code"])
            if error:
                errors["base"] = error
            else:
                return await self.async_step_select_home()

        return self.async_show_form(
            step_id="mfa",
            data_schema=MFA_SCHEMA,
            description_placeholders={"mfa_type": self._get_mfa_type_display()},
            errors=errors,
        )

    async def async_step_install(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create config entry at completion of flow."""
        entry_data = {
            CONF_EMAIL: self.username,
            CONF_HOME_ID: self.home_id,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

        homes = await self.api.user.get_homes()
        home_name = next(
            (home["homename"] for home in homes if home["homeid"] == self.home_id),
            f"Kwikset Home {self.home_id}",
        )

        return self.async_create_entry(
            title=home_name,
            data=entry_data,
            options={CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL},
        )

    # -------------------------------------------------------------------------
    # Options flow
    # -------------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow handler."""
        return KwiksetOptionsFlow()


class KwiksetOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Kwikset integration.

    Allows configuration of:
        - Refresh interval: How often to poll the Kwikset cloud (15-60 seconds)
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_REFRESH_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=15,
                            max=60,
                        )
                    ),
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
