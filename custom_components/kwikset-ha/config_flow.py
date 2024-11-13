from typing import Any
from collections.abc import Mapping

from aiokwikset import API
from aiokwikset.errors import RequestError
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

    entry: config_entries.ConfigEntry | None

    def __init__(self):
        """Create a new instance of the flow handler"""
        self.api = None
        self.username = None
        self.password = None
        self.home_id = None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with kwikset"""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_user()
    
    async def async_step_reauth_user(self, user_input=None):
        """Get the email and password from the user"""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("email"): str,
                        vol.Required("password"): str
                    }
                ),
                errors = errors
            )
            
        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        try:
            #initialize API
            self.api = API()
            #start authentication
            await self.api.async_login(self.username,self.password)

            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    CONF_EMAIL: self.username,
                    CONF_HOME_ID: self.home_id,
                    CONF_ACCESS_TOKEN: self.api.access_token,
                    CONF_REFRESH_TOKEN: self.api.refresh_token,
                }
            )
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        
        except RequestError as request_error:
            LOGGER.error("Error connecting to the kwikset API: %s", request_error)
            errors["base"] = "cannot_connect"
            raise CannotConnect from request_error

    async def async_step_user(self, user_input=None):
        """Get the email and password from the user"""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("email"): str,
                        vol.Required("password"): str
                    }
                ),
                errors = errors
            )
            
        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        return await self.async_step_select_home()

    async def async_step_select_home(self, user_input=None):
        """Ask user to select the home to setup"""
        errors: dict[str, str] = {}

        if user_input is None or CONF_HOME_ID not in user_input:
            try:
                #initialize API
                self.api = API()
                #start authentication
                await self.api.async_login(self.username,self.password)
            
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
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)
            
class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", 
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_REFRESH_INTERVAL, default=self.config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=15,
                            max=60
                        )
                    )
                }
            )
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""