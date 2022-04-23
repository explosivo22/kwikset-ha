from aiokwikset import API
from aiokwikset.errors import RequestError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_CODE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import callback

from .const import (
    DOMAIN, 
    LOGGER,
    POOL_ID,
    CLIENT_ID,
    POOL_REGION,
    CONF_API,
    CONF_HOME_ID
)

class KwiksetFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of Kwikset integrations."""

    VERSION = 2

    def __init__(self):
        """Create a new instance of the flow handler"""
        self.access_token = None
        self.id_token = None
        self.refresh_token = None
        self.api = None
        self.username = None
        self.password = None
        self.home_id = None


    async def async_step_user(self, user_input=None):
        """Get the email and password from the user"""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str
                    }
                ),
                errors = errors
            )

        return await self.async_step_code()
        
        

    async def async_step_code(self, user_input=None):
        """Get the Verification code from the user"""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="verification_code",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CODE): str
                    }
                ),
                errors = errors
            )
        for entry in self._async_current_entries():
            try:
                #initialize API
                self.api = API(entry.data[CONF_EMAIL])
                #start authentication
                pre_auth = await self.api.authenticate(entry.data[CONF_PASSWORD])
                #MFA verification
                await self.api.verify_user(pre_auth, user_input[CONF_CODE])
            
            except RequestError as request_error:
                LOGGER.error("Error connecting to the kwikset API: %s", request_error)
                raise CannotConnect from request_error

            return self.async_step_select_home()

    async def async_step_select_home(self, user_input=None):
        """Ask user to select the home to setup"""
        if user_input is None or CONF_HOME_ID not in user_input:
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
        return await self.async_step_install()

    async def async_step_install(self, data=None):
        """Create a config entry at completion of a flow and authorization"""
        data = {
            CONF_API: self.api,
            CONF_HOME_ID: self.home_id
        }

        homes = await self.api.user.get_homes()
        for home in homes:
            if home['homeid'] == data[CONF_HOME_ID]:
                home_name = home['homename']
                return self.async_create_entry(title=home_name, data=data)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""