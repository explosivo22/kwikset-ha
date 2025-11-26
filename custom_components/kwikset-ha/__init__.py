"""Support for Kwikset Smart Locks integration.

This module is the entry point for the Kwikset integration. It handles:
- Config entry setup and teardown
- Initial authentication and token refresh
- Device discovery and coordinator creation
- Periodic device polling for new/removed devices
- Config entry migrations for version upgrades

Architecture Overview:
    The integration uses a DataUpdateCoordinator pattern where each physical
    Kwikset lock has its own coordinator. This allows independent polling
    and failure isolation per device.

    Data Flow:
        Kwikset Cloud API ← aiokwikset library ← KwiksetDeviceDataUpdateCoordinator
                                                            ↓
                                            entry.runtime_data.devices[device_id]
                                                            ↓
                                            Entity platforms (lock, sensor, switch)

Platinum Quality Scale Compliance:
    - runtime_data: Uses typed KwiksetRuntimeData dataclass
    - async_dependency: aiokwikset is fully async
    - strict_typing: Full type annotations with py.typed marker
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from aiokwikset import API
from aiokwikset.api import Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_HOME_ID,
    CONF_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)
from .device import KwiksetDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms this integration provides entities for
PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR, Platform.SWITCH]


@dataclass
class KwiksetRuntimeData:
    """Runtime data stored in config entry for the Kwikset integration.

    This dataclass holds all runtime state needed by the integration:
    - client: The authenticated API client for making API calls
    - devices: Dictionary mapping device_id to its coordinator
    - known_devices: Set of device IDs for tracking new/removed devices

    Using a dataclass provides:
    - Type safety with proper annotations
    - Clear structure for runtime state
    - Platinum tier compliance for runtime_data pattern
    """

    client: API
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = field(default_factory=dict)
    known_devices: set[str] = field(default_factory=set)


# Type alias for config entries with typed runtime_data
# This enables type checking when accessing entry.runtime_data
# Uses PEP 695 type alias syntax (Python 3.12+)
type KwiksetConfigEntry = ConfigEntry[KwiksetRuntimeData]

# Export for use by other modules
__all__ = ["KwiksetConfigEntry", "KwiksetRuntimeData"]

async def async_setup_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Set up Kwikset from a config entry.

    This function is called by Home Assistant when a config entry is loaded.
    It performs the following steps:
    1. Authenticate with the Kwikset cloud API using stored tokens
    2. Refresh tokens if needed and save new tokens back to config entry
    3. Fetch list of devices from the selected home
    4. Create a coordinator for each device
    5. Perform initial data fetch for all coordinators
    6. Set up entity platforms
    7. Register periodic device discovery

    Raises:
        ConfigEntryAuthFailed: If authentication fails (triggers reauth flow)
        ConfigEntryNotReady: If there's a temporary connection issue
    """
    # Initialize API client (does not make network calls yet)
    client = API()

    try:
        # Authenticate using stored tokens - this refreshes them if needed
        await client.async_renew_access_token(
            entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_REFRESH_TOKEN]
        )

        # Persist refreshed tokens to config entry for next startup
        # This ensures tokens survive HA restarts without re-authentication
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

        # Validate authentication by fetching user info
        user_info = await client.user.get_info()
    except Unauthenticated as err:
        # Token refresh failed - user needs to re-authenticate
        raise ConfigEntryAuthFailed(err) from err
    except RequestError as err:
        # Transient network error - HA will retry setup later
        raise ConfigEntryNotReady from err
    _LOGGER.debug("Kwikset user information: %s", user_info)

    # Fetch all devices from the configured home
    api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])

    # Get polling interval from options (user-configurable 15-60 seconds)
    update_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    # Create a coordinator for each device
    # Each coordinator manages its own polling and state for one lock
    devices_dict: dict[str, KwiksetDeviceDataUpdateCoordinator] = {}
    for device in api_devices:
        device_id = device["deviceid"]
        devices_dict[device_id] = KwiksetDeviceDataUpdateCoordinator(
            hass, client, device_id, device["devicename"], update_interval, entry
        )

    # Store runtime data using typed ConfigEntry pattern (Platinum tier)
    entry.runtime_data = KwiksetRuntimeData(
        client=client,
        devices=devices_dict,
        known_devices=set(devices_dict.keys()),
    )

    # Fetch initial data for all coordinators using first_refresh
    # This raises ConfigEntryNotReady if any coordinator fails
    for device_coordinator in devices_dict.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Forward setup to entity platforms (lock, sensor, switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options flow changes
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Start periodic device discovery (every 5 minutes)
    # This detects new devices added to the Kwikset account
    async def _async_check_devices(_now) -> None:
        """Periodically check for new or removed devices."""
        await _async_update_devices(hass, entry)

    entry.async_on_unload(
        async_track_time_interval(hass, _async_check_devices, timedelta(minutes=5))
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def _async_update_devices(hass: HomeAssistant, entry: KwiksetConfigEntry) -> None:
    """Check for new or removed devices and update accordingly."""
    runtime_data = entry.runtime_data
    client = runtime_data.client
    devices_dict = runtime_data.devices
    known_devices = runtime_data.known_devices
    device_registry = dr.async_get(hass)

    try:
        # Fetch current devices from API
        api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])
        current_device_ids = {device["deviceid"] for device in api_devices}

        # Find new devices
        new_device_ids = current_device_ids - known_devices
        if new_device_ids:
            _LOGGER.info(
                "Discovered %d new device(s): %s", len(new_device_ids), new_device_ids
            )

            # Get update interval
            update_interval = entry.options.get(
                CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
            )

            # Create coordinators for new devices
            for device in api_devices:
                device_id = device["deviceid"]
                if device_id in new_device_ids:
                    coordinator = KwiksetDeviceDataUpdateCoordinator(
                        hass, client, device_id, device["devicename"], update_interval, entry
                    )
                    await coordinator.async_config_entry_first_refresh()
                    devices_dict[device_id] = coordinator
                    known_devices.add(device_id)

            # Fire event to notify platforms about new devices
            # This is safer than reloading during runtime
            hass.bus.async_fire(
                f"{DOMAIN}_new_device",
                {"entry_id": entry.entry_id, "device_ids": list(new_device_ids)},
            )

        # Find removed devices
        removed_device_ids = known_devices - current_device_ids
        if removed_device_ids:
            _LOGGER.info(
                "Detected %d removed device(s): %s",
                len(removed_device_ids),
                removed_device_ids,
            )

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

async def _async_options_updated(
    hass: HomeAssistant, entry: KwiksetConfigEntry
) -> None:
    """Handle options update.

    Update coordinator intervals dynamically without reloading the integration.
    This follows Home Assistant best practices by avoiding reload during setup.
    """
    devices_dict = entry.runtime_data.devices

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
                old_interval.total_seconds() if old_interval else None,
                new_interval,
            )
            # Trigger an immediate refresh with the new interval
            await device_coordinator.async_request_refresh()

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: KwiksetConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
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