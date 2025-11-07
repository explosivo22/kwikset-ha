"""Support for Kwikset integration."""
import logging
import asyncio
from datetime import timedelta

from aiokwikset import API
from aiokwikset.api import Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

# Type for tracking device IDs
type KwiksetDeviceDict = dict[str, KwiksetDeviceDataUpdateCoordinator]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kwikset from config entry"""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    _LOGGER.debug(entry.data[CONF_EMAIL])

    hass.data[DOMAIN][entry.entry_id][CLIENT] = client = API()

    try:
        await client.async_renew_access_token(entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_REFRESH_TOKEN])
        
        # Save the refreshed tokens back to the entry
        if client.access_token != entry.data[CONF_ACCESS_TOKEN]:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ACCESS_TOKEN: client.access_token,
                    CONF_REFRESH_TOKEN: client.refresh_token,
                },
            )
            _LOGGER.debug("Tokens refreshed and saved to config entry")
        
        user_info = await client.user.get_info()
    except Unauthenticated as err:
        raise ConfigEntryAuthFailed(err) from err
    except RequestError as err:
        raise ConfigEntryNotReady from err
    _LOGGER.debug("Kwikset user information: %s", user_info)

    # Fetch devices from API
    api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])

    if CONF_REFRESH_INTERVAL in entry.options:
        update_interval = entry.options[CONF_REFRESH_INTERVAL]
    else:
        update_interval = DEFAULT_REFRESH_INTERVAL

    # Create coordinators for all devices
    # Store as dict for easy lookup by device ID
    devices_dict: KwiksetDeviceDict = {}
    for device in api_devices:
        device_id = device["deviceid"]
        devices_dict[device_id] = KwiksetDeviceDataUpdateCoordinator(
            hass, client, device_id, device["devicename"], update_interval
        )

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices_dict
    hass.data[DOMAIN][entry.entry_id]["known_devices"] = set(devices_dict.keys())

    # Fetch initial data using async_config_entry_first_refresh
    # This will call _async_setup and then _async_update_data
    # Will raise ConfigEntryNotReady if the refresh fails
    for device_coordinator in devices_dict.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register periodic check for new/removed devices
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    
    # Start periodic device discovery check
    async def _async_check_devices(_now):
        """Periodically check for new or removed devices."""
        await _async_update_devices(hass, entry)
    
    # Schedule device check every 5 minutes
    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_check_devices, timedelta(minutes=5)
        )
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def _async_update_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Check for new or removed devices and update accordingly."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    devices_dict: KwiksetDeviceDict = hass.data[DOMAIN][entry.entry_id]["devices"]
    known_devices: set[str] = hass.data[DOMAIN][entry.entry_id]["known_devices"]
    device_registry = dr.async_get(hass)
    
    try:
        # Fetch current devices from API
        api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])
        current_device_ids = {device["deviceid"] for device in api_devices}
        
        # Find new devices
        new_device_ids = current_device_ids - known_devices
        if new_device_ids:
            _LOGGER.info("Discovered %d new device(s): %s", len(new_device_ids), new_device_ids)
            
            # Get update interval
            update_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
            
            # Create coordinators for new devices
            for device in api_devices:
                device_id = device["deviceid"]
                if device_id in new_device_ids:
                    coordinator = KwiksetDeviceDataUpdateCoordinator(
                        hass, client, device_id, device["devicename"], update_interval
                    )
                    await coordinator.async_config_entry_first_refresh()
                    devices_dict[device_id] = coordinator
                    known_devices.add(device_id)
            
            # Fire event to notify platforms about new devices
            # This is safer than reloading during runtime
            hass.bus.async_fire(
                f"{DOMAIN}_new_device",
                {"entry_id": entry.entry_id, "device_ids": list(new_device_ids)}
            )
        
        # Find removed devices
        removed_device_ids = known_devices - current_device_ids
        if removed_device_ids:
            _LOGGER.info("Detected %d removed device(s): %s", len(removed_device_ids), removed_device_ids)
            
            # Remove from device registry
            for device_id in removed_device_ids:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=entry.entry_id,
                    )
                    _LOGGER.debug("Removed device %s from registry", device_id)
                
                # Remove coordinator
                if device_id in devices_dict:
                    del devices_dict[device_id]
                known_devices.discard(device_id)
    
    except (Unauthenticated, RequestError) as err:
        _LOGGER.error("Error checking for device changes: %s", err)

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.
    
    Update coordinator intervals dynamically without reloading the integration.
    This follows Home Assistant best practices by avoiding reload during setup.
    """
    devices_dict: KwiksetDeviceDict = hass.data[DOMAIN][entry.entry_id].get("devices", {})
    
    if not devices_dict:
        # No devices yet, just return
        return
    
    # Get the new update interval
    new_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
    new_interval_td = timedelta(seconds=new_interval)
    
    # Update each coordinator's update interval
    for device_coordinator in devices_dict.values():
        old_interval = device_coordinator.update_interval
        
        if old_interval != new_interval_td:
            device_coordinator.update_interval = new_interval_td
            _LOGGER.debug(
                "Updated refresh interval for %s from %s to %s seconds",
                device_coordinator.device_name,
                old_interval.total_seconds(),
                new_interval,
            )
            # Trigger an immediate refresh with the new interval
            await device_coordinator.async_request_refresh()

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