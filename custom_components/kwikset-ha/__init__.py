import logging
import asyncio

from aiokwikset import API
from aiokwikset.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_HOME_ID,
    CONF_REFRESH_TOKEN,
    CLIENT
)
from .device import KwiksetDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["lock", "sensor", "switch"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kwikset from config entry"""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    _LOGGER.debug(entry.data[CONF_EMAIL])

    hass.data[DOMAIN][entry.entry_id][CLIENT] = client = API(entry.data[CONF_EMAIL], refresh_token=entry.data[CONF_REFRESH_TOKEN])

    try:
        await client.renew_access_token()
        user_info = await client.user.get_info()
    except RequestError as err:
        raise ConfigEntryNotReady from err

    _LOGGER.debug("Kwikset user information: %s", user_info)

    devices = await client.device.get_devices(entry.data[CONF_HOME_ID])

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        KwiksetDeviceDataUpdateCoordinator(hass, client, device["deviceid"], device["devicename"])
        for device in devices
    ]

    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok