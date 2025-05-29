import logging
import asyncio

from aiokwikset import API
from aiokwikset.api import Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_HOME_ID,
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

    hass.data[DOMAIN][entry.entry_id][CLIENT] = client = API()

    try:
        await client.async_renew_access_token(entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_REFRESH_TOKEN])
        #await client.async_login(entry.data[CONF_EMAIL], entry.data[CONF_REFRESH_TOKEN])
        user_info = await client.user.get_info()
    except Unauthenticated as err:
        raise ConfigEntryAuthFailed(err) from err
    except RequestError as err:
        raise ConfigEntryNotReady from err
    _LOGGER.debug("Kwikset user information: %s", user_info)

    devices = await client.device.get_devices(entry.data[CONF_HOME_ID])

    if CONF_REFRESH_INTERVAL in entry.options:
        update_interval = entry.options[CONF_REFRESH_INTERVAL]
    else:
        update_interval = DEFAULT_REFRESH_INTERVAL

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        KwiksetDeviceDataUpdateCoordinator(hass, client, device["deviceid"], device["devicename"], update_interval)
        for device in devices
    ]

    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    if not entry.options:
        await _async_options_updated(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:

        # TODO: Do some changes which is not stored in the config entry itself

        # There's no need to call async_update_entry, the config entry will automatically be
        # saved when async_migrate_entry returns True
        config_entry.version = 2

    if config_entry.version == 2:
        data = {**config_entry.data}

        if not data.get(CONF_ACCESS_TOKEN):
            data[CONF_ACCESS_TOKEN] = config_entry.data[CONF_REFRESH_TOKEN]

        hass.config_entries.async_update_entry(config_entry, data=data, version=3)

    if config_entry.version == 3:
        data = {**config_entry.data}

        if not data.get(CONF_REFRESH_INTERVAL):
            data[CONF_REFRESH_INTERVAL] = DEFAULT_REFRESH_INTERVAL

        hass.config_entries.async_update_entry(config_entry, data=data, version=4)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True