from typing import Any
from collections.abc import Mapping

from aiokwikset import API
from aiokwikset.errors import RequestError, MFAChallengeRequired
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_CODE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import (
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN, 
    LOGGER,
    CONF_HOME_ID,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_INTERVAL
)

CODE_TYPES = ['email','phone']

class KwiksetFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of Kwikset integrations."""

    VERSION = 4

    def __init__(self):
        """Create a new instance of the flow handler"""
        self.api = None
        self.username = None
        self.password = None
        self.home_id = None
        self.mfa_type = None
        self.mfa_tokens = None
    
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        # Store entry data for use in reauth_confirm
        self.username = entry_data.get(CONF_EMAIL)
        self.home_id = entry_data.get(CONF_HOME_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self.username = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]

            try:
                # Initialize API and authenticate
                self.api = API()
                await self.api.async_login(self.username, self.password)
                
                # Successfully authenticated, update the entry
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_EMAIL: self.username,
                        CONF_ACCESS_TOKEN: self.api.access_token,
                        CONF_REFRESH_TOKEN: self.api.refresh_token,
                    },
                )
            
            except MFAChallengeRequired as mfa_error:
                # MFA is required during reauth - store challenge info and show MFA step
                LOGGER.debug("MFA challenge required during reauth: %s", mfa_error.mfa_type)
                self.mfa_type = mfa_error.mfa_type
                self.mfa_tokens = mfa_error.mfa_tokens
                return await self.async_step_mfa_reauth()
            
            except RequestError as request_error:
                LOGGER.error("Error connecting to the Kwikset API: %s", request_error)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"

        # Show the reauth form
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
    ) -> FlowResult:
        """Handle MFA verification during reauthentication."""
        errors: dict[str, str] = {}
        
        if user_input is None:
            # Determine MFA type for display
            mfa_type_display = (
                "authenticator app" if self.mfa_type == "SOFTWARE_TOKEN_MFA" 
                else "SMS"
            )
            
            return self.async_show_form(
                step_id="mfa_reauth",
                data_schema=vol.Schema({
                    vol.Required("mfa_code"): str,
                }),
                description_placeholders={
                    "mfa_type": mfa_type_display
                },
                errors=errors
            )
        
        try:
            # Complete MFA authentication
            await self.api.async_respond_to_mfa_challenge(
                mfa_code=user_input["mfa_code"],
                mfa_type=self.mfa_type,
                mfa_tokens=self.mfa_tokens
            )
            LOGGER.debug("MFA authentication successful during reauth")
            
            # Successfully authenticated, update the entry
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={
                    CONF_EMAIL: self.username,
                    CONF_ACCESS_TOKEN: self.api.access_token,
                    CONF_REFRESH_TOKEN: self.api.refresh_token,
                },
            )
            
        except RequestError as err:
            LOGGER.error("MFA verification failed during reauth: %s", err)
            errors["base"] = "invalid_mfa"
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error during MFA verification in reauth")
            errors["base"] = "unknown"
        
        # Show form again with error
        mfa_type_display = (
            "authenticator app" if self.mfa_type == "SOFTWARE_TOKEN_MFA" 
            else "SMS"
        )
        return self.async_show_form(
            step_id="mfa_reauth",
            data_schema=vol.Schema({
                vol.Required("mfa_code"): str,
            }),
            description_placeholders={
                "mfa_type": mfa_type_display
            },
            errors=errors
        )
    
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration to discover new devices."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Get the current config entry
            entry = self._get_reconfigure_entry()
            
            try:
                # Re-authenticate with stored credentials
                self.api = API()
                await self.api.async_renew_access_token(
                    entry.data[CONF_ACCESS_TOKEN],
                    entry.data[CONF_REFRESH_TOKEN]
                )
                
                # Successfully authenticated, reload to discover new devices
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: self.api.access_token,
                        CONF_REFRESH_TOKEN: self.api.refresh_token,
                    },
                )
            except RequestError as request_error:
                LOGGER.error("Error connecting to the Kwikset API: %s", request_error)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during reconfiguration")
                errors["base"] = "unknown"
        
        # Show the reconfigure form
        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "info": "This will reload the integration and discover any new devices."
            },
            errors=errors,
        )

        

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get the email and password from the user"""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str
                    }
                ),
                errors=errors
            )
            
        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        return await self.async_step_select_home()

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user to select the home to setup"""
        errors: dict[str, str] = {}

        if user_input is None or CONF_HOME_ID not in user_input:
            try:
                # Initialize API
                self.api = API()
                # Start authentication
                await self.api.async_login(self.username, self.password)
            
            except MFAChallengeRequired as mfa_error:
                # MFA is required - store challenge info and show MFA step
                LOGGER.debug("MFA challenge required: %s", mfa_error.mfa_type)
                self.mfa_type = mfa_error.mfa_type
                self.mfa_tokens = mfa_error.mfa_tokens
                return await self.async_step_mfa()
            
            except RequestError as request_error:
                LOGGER.error("Error connecting to the kwikset API: %s", request_error)
                errors["base"] = "cannot_connect"
                raise CannotConnect from request_error

            #Get available locations
            existing_homes = [
                entry.data[CONF_HOME_ID] for entry in self._async_current_entries()
            ]
            homes = await self.api.user.get_homes()
            homes_options = {
                home['homeid']: home['homename']
                for home in homes
                if home['homeid'] not in existing_homes
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
        await self.async_set_unique_id(f"{self.home_id}")
        self._abort_if_unique_id_configured()
        return await self.async_step_install()

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle MFA verification."""
        errors: dict[str, str] = {}
        
        if user_input is None:
            # Determine MFA type for display
            mfa_type_display = (
                "authenticator app" if self.mfa_type == "SOFTWARE_TOKEN_MFA" 
                else "SMS"
            )
            
            return self.async_show_form(
                step_id="mfa",
                data_schema=vol.Schema({
                    vol.Required("mfa_code"): str,
                }),
                description_placeholders={
                    "mfa_type": mfa_type_display
                },
                errors=errors
            )
        
        try:
            # Complete MFA authentication
            await self.api.async_respond_to_mfa_challenge(
                mfa_code=user_input["mfa_code"],
                mfa_type=self.mfa_type,
                mfa_tokens=self.mfa_tokens
            )
            LOGGER.debug("MFA authentication successful")
            
            # Continue with home selection
            return await self.async_step_select_home()
            
        except RequestError as err:
            LOGGER.error("MFA verification failed: %s", err)
            errors["base"] = "invalid_mfa"
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error during MFA verification")
            errors["base"] = "unknown"
        
        # Show form again with error
        mfa_type_display = (
            "authenticator app" if self.mfa_type == "SOFTWARE_TOKEN_MFA" 
            else "SMS"
        )
        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema({
                vol.Required("mfa_code"): str,
            }),
            description_placeholders={
                "mfa_type": mfa_type_display
            },
            errors=errors
        )

    async def async_step_install(self, data=None):
        """Create a config entry at completion of a flow and authorization"""
        data = {
            CONF_EMAIL: self.username,
            CONF_HOME_ID: self.home_id,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

        homes = await self.api.user.get_homes()
        for home in homes:
            if home['homeid'] == data[CONF_HOME_ID]:
                home_name = home['homename']
                return self.async_create_entry(
                    title=home_name, 
                    data=data, 
                    options={
                        CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
                    },)
            
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow()
            
class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Kwikset integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
                            CONF_REFRESH_INTERVAL, 
                            DEFAULT_REFRESH_INTERVAL
                        )
                    ): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=15,
                            max=60
                        )
                    ),
                }
            )
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""