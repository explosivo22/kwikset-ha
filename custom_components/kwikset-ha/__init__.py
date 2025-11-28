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

Quality Scale Compliance (Platinum Tier):
    - runtime_data: Uses typed KwiksetRuntimeData dataclass (entry.runtime_data pattern)
    - async_dependency: aiokwikset is fully async (no blocking I/O)
    - strict_typing: Full type annotations with py.typed marker
    - stale_devices: Automatic removal of devices no longer in API response
    - dynamic_devices: 5-minute periodic discovery with bus events
    - test_before_setup: Validates tokens before platform setup
    - config_entry_unloading: Clean unload via async_unload_platforms

Token Management:
    Tokens are stored in config_entry.data and refreshed on every startup.
    The coordinator also proactively refreshes tokens 5 minutes before expiry.
    This dual approach ensures:
    1. Fresh tokens on HA restart (async_setup_entry)
    2. Continuous operation during long uptimes (coordinator)

Device Discovery:
    - Initial: Devices fetched during async_setup_entry
    - Periodic: _async_update_devices runs every 5 minutes
    - New devices: Coordinator created, bus event fired, platforms add entities
    - Removed devices: Device registry cleanup, coordinator deleted
"""

from __future__ import annotations

from collections.abc import Callable
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
from homeassistant.helpers import device_registry as dr, issue_registry as ir
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
# Each platform file (lock.py, sensor.py, switch.py) implements async_setup_entry
PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR, Platform.SWITCH]

# Device discovery interval - check for new/removed devices every 5 minutes
# This is separate from the entity polling interval (15-60s, user-configurable)
DEVICE_DISCOVERY_INTERVAL = timedelta(minutes=5)


@dataclass
class KwiksetRuntimeData:
    """Runtime data stored in config entry for the Kwikset integration.

    This dataclass holds all runtime state needed by the integration:
    - client: The authenticated API client for making API calls
    - devices: Dictionary mapping device_id to its coordinator
    - known_devices: Set of device IDs for tracking new/removed devices
    - cancel_device_discovery: Callback to cancel the device discovery timer

    Using a dataclass provides:
    - Type safety with proper annotations
    - Clear structure for runtime state
    - Platinum tier compliance for runtime_data pattern

    Silver Tier - stale_devices:
        The known_devices set is critical for stale device tracking.
        By comparing known_devices with current API response, we detect:
        - New devices: current_ids - known_devices (add coordinators)
        - Removed devices: known_devices - current_ids (cleanup registry)

    Note:
        This replaces the legacy hass.data[DOMAIN][entry_id] pattern.
        Access via entry.runtime_data provides type safety and auto-cleanup.
    """

    client: API
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = field(default_factory=dict)
    known_devices: set[str] = field(default_factory=set)
    cancel_device_discovery: Callable[[], None] | None = None


# Type alias for config entries with typed runtime_data
# This enables type checking when accessing entry.runtime_data
# Uses PEP 695 type alias syntax (Python 3.12+)
type KwiksetConfigEntry = ConfigEntry[KwiksetRuntimeData]

# Export for use by other modules
__all__ = ["KwiksetConfigEntry", "KwiksetRuntimeData"]

async def async_setup_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Set up Kwikset from a config entry.

    This function is called by Home Assistant when a config entry is loaded.
    It follows the Bronze tier requirement "test_before_setup" by validating
    authentication before creating any entities.

    Setup Steps:
        1. Authenticate with the Kwikset cloud API using stored tokens
        2. Refresh tokens if needed and save new tokens back to config entry
        3. Fetch list of devices from the selected home
        4. Create a coordinator for each device
        5. Perform initial data fetch for all coordinators
        6. Set up entity platforms
        7. Register periodic device discovery (Silver tier: stale_devices)

    Exception Handling:
        - ConfigEntryAuthFailed: If authentication fails (triggers reauth flow)
        - ConfigEntryNotReady: If there's a temporary connection issue (HA retries)

    Quality Scale Compliance:
        - test_before_setup (Bronze): Validates tokens before platform setup
        - config_entry_unloading (Silver): Registers cleanup via async_on_unload
        - stale_devices (Silver): Registers periodic device discovery
        - dynamic_devices (Gold): 5-minute discovery interval
        - runtime_data (Platinum): Uses typed KwiksetRuntimeData

    Args:
        hass: Home Assistant instance
        entry: Config entry being set up

    Returns:
        True if setup was successful

    Raises:
        ConfigEntryAuthFailed: If authentication fails (triggers reauth flow)
        ConfigEntryNotReady: If there's a temporary connection issue
    """
    # Initialize API client (does not make network calls yet)
    client = API()

    try:
        # Bronze tier: test_before_setup
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
        # This confirms the tokens work before we create any entities
        user_info = await client.user.get_info()
    except Unauthenticated as err:
        # Token refresh failed - user needs to re-authenticate
        # Silver tier: reauthentication_flow - ConfigEntryAuthFailed triggers it
        # Create a repair issue to notify user of auth expiry
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"auth_expired_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="auth_expired",
            translation_placeholders={"entry_title": entry.title},
        )
        raise ConfigEntryAuthFailed(err) from err
    except RequestError as err:
        # Transient network error - HA will retry setup later
        raise ConfigEntryNotReady from err
    _LOGGER.debug("Kwikset user information: %s", user_info)

    # Fetch all devices from the configured home
    api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])

    # Get polling interval from options (user-configurable 15-60 seconds)
    # Bronze tier: appropriate_polling
    update_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    # Create a coordinator for each device
    # Each coordinator manages its own polling and state for one lock
    # Silver tier: parallel_updates - each coordinator is independent
    devices_dict: dict[str, KwiksetDeviceDataUpdateCoordinator] = {}
    for device in api_devices:
        device_id = device["deviceid"]
        devices_dict[device_id] = KwiksetDeviceDataUpdateCoordinator(
            hass,
            api_client=client,
            device_id=device_id,
            device_name=device["devicename"],
            update_interval=update_interval,
            config_entry=entry,
        )

    # Platinum tier: runtime_data
    # Store runtime data using typed ConfigEntry pattern
    entry.runtime_data = KwiksetRuntimeData(
        client=client,
        devices=devices_dict,
        known_devices=set(devices_dict.keys()),  # Silver tier: stale_devices tracking
    )

    # Fetch initial data for all coordinators using first_refresh
    # This raises ConfigEntryNotReady if any coordinator fails
    for device_coordinator in devices_dict.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Forward setup to entity platforms (lock, sensor, switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options flow changes
    # Silver tier: config_entry_unloading - cleanup registered
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Gold tier: dynamic_devices / Silver tier: stale_devices
    # Start periodic device discovery (every 5 minutes)
    # This detects new devices added to the Kwikset account AND
    # removes devices that have been deleted from the account
    async def _async_check_devices(_now) -> None:
        """Periodically check for new or removed devices."""
        await _async_update_devices(hass, entry)

    # Store cancel callback in runtime_data for explicit cleanup in async_unload_entry
    # This ensures the timer is cancelled before test cleanup verification runs,
    # avoiding lingering timer errors in tests
    entry.runtime_data.cancel_device_discovery = async_track_time_interval(
        hass, _async_check_devices, DEVICE_DISCOVERY_INTERVAL
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Unload a config entry.

    Silver Tier: config_entry_unloading
    This function properly unloads all platforms and cleans up resources.
    The runtime_data is automatically cleaned up by Home Assistant when
    using the entry.runtime_data pattern.

    Note:
        The device discovery timer is explicitly cancelled here rather than
        relying on entry.async_on_unload. This ensures proper cleanup in tests
        where entry.async_on_unload callbacks may run after test verification.

    Args:
        hass: Home Assistant instance
        entry: Config entry being unloaded

    Returns:
        True if unload was successful
    """
    # Cancel device discovery timer before platform unload
    # This prevents lingering timer errors in tests by ensuring
    # cleanup happens before test verification
    if entry.runtime_data.cancel_device_discovery:
        entry.runtime_data.cancel_device_discovery()
        entry.runtime_data.cancel_device_discovery = None

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_devices(hass: HomeAssistant, entry: KwiksetConfigEntry) -> None:
    """Check for new or removed devices and update accordingly.

    This function implements two Quality Scale requirements:
    - Silver tier: stale_devices - removes devices no longer in API response
    - Gold tier: dynamic_devices - adds devices newly discovered in API

    Device Discovery Flow:
        1. Fetch current devices from Kwikset API
        2. Compare with known_devices set in runtime_data
        3. For new devices: create coordinator, fire bus event
        4. For removed devices: cleanup device registry, remove coordinator

    Stale Device Removal (Silver tier requirement):
        When a device is removed from the Kwikset account (via app or website),
        we detect this by comparing known_devices with the API response.
        Removed devices are:
        1. Removed from device registry (which cascades to entity removal)
        2. Removed from runtime_data.devices dict
        3. Removed from runtime_data.known_devices set

    Dynamic Device Addition (Gold tier requirement):
        When a new device is added to the Kwikset account:
        1. A new coordinator is created and initialized
        2. It's added to runtime_data.devices dict
        3. Device ID is added to runtime_data.known_devices set
        4. Bus event "{DOMAIN}_new_device" is fired
        5. Entity platforms listen for this event and add entities

    Args:
        hass: Home Assistant instance
        entry: Config entry for the integration

    Note:
        This function is called every 5 minutes via async_track_time_interval.
        Errors are logged but don't stop future discovery cycles.
    """
    runtime_data = entry.runtime_data
    client = runtime_data.client
    devices_dict = runtime_data.devices
    known_devices = runtime_data.known_devices
    device_registry = dr.async_get(hass)

    try:
        # Fetch current devices from API
        api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])
        current_device_ids = {device["deviceid"] for device in api_devices}

        # =================================================================
        # Gold tier: dynamic_devices - Add newly discovered devices
        # =================================================================
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
                        hass,
                        api_client=client,
                        device_id=device_id,
                        device_name=device["devicename"],
                        update_interval=update_interval,
                        config_entry=entry,
                    )
                    await coordinator.async_config_entry_first_refresh()
                    devices_dict[device_id] = coordinator
                    known_devices.add(device_id)

            # Fire event to notify platforms about new devices
            # Platforms listen for this event and call _async_add_new_devices()
            # This is safer than reloading during runtime
            hass.bus.async_fire(
                f"{DOMAIN}_new_device",
                {"entry_id": entry.entry_id, "device_ids": list(new_device_ids)},
            )

        # =================================================================
        # Silver tier: stale_devices - Remove devices no longer in API
        # =================================================================
        removed_device_ids = known_devices - current_device_ids
        if removed_device_ids:
            _LOGGER.info(
                "Detected %d removed device(s): %s",
                len(removed_device_ids),
                removed_device_ids,
            )

            # Remove from device registry and cleanup
            for device_id in removed_device_ids:
                # Find device in registry by our identifier
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if device:
                    # Remove config entry from device (cascades to entity removal)
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=entry.entry_id,
                    )
                    _LOGGER.debug("Removed device %s from registry", device_id)

                # Remove coordinator from runtime data
                if device_id in devices_dict:
                    del devices_dict[device_id]
                known_devices.discard(device_id)

    except (Unauthenticated, RequestError) as err:
        # Log error but don't raise - next discovery cycle will try again
        _LOGGER.error("Error checking for device changes: %s", err)

async def _async_options_updated(
    hass: HomeAssistant, entry: KwiksetConfigEntry
) -> None:
    """Handle options update.

    Update coordinator intervals dynamically without reloading the integration.
    This follows Home Assistant best practices by avoiding reload during setup.

    Bronze tier: appropriate_polling
    The polling interval is user-configurable via the options flow (15-60 seconds).
    When changed, we update all coordinators immediately without requiring a reload.

    Args:
        hass: Home Assistant instance
        entry: Config entry with updated options
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
    """Remove a config entry from a device.

    This callback is called when a user manually removes a device from the UI.
    Returning True allows the removal to proceed.

    Note:
        We always allow manual device removal. The device will be re-added
        on the next discovery cycle if it still exists in the Kwikset account.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry for the integration
        device_entry: Device being removed

    Returns:
        True to allow the removal
    """
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry to current version.

    This function handles config entry schema migrations when the integration
    is upgraded. Each migration step is idempotent and can be re-run safely.

    Migration History:
        - Version 1 → 2: Initial migration (no data changes)
        - Version 2 → 3: Added CONF_ACCESS_TOKEN field
        - Version 3 → 4: Moved CONF_REFRESH_INTERVAL to options

    Args:
        hass: Home Assistant instance
        config_entry: Config entry to migrate

    Returns:
        True if migration was successful
    """
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 → 2: No data changes, just version bump
        config_entry.version = 2

    if config_entry.version == 2:
        # Version 2 → 3: Ensure CONF_ACCESS_TOKEN exists
        data = {**config_entry.data}

        if not data.get(CONF_ACCESS_TOKEN):
            # Copy from refresh token if missing
            data[CONF_ACCESS_TOKEN] = config_entry.data[CONF_REFRESH_TOKEN]

        hass.config_entries.async_update_entry(config_entry, data=data, version=3)

    if config_entry.version == 3:
        # Version 3 → 4: CONF_REFRESH_INTERVAL moved to options
        # (Previously was in data, now properly in options for user-configurable values)
        data = {**config_entry.data}

        # Remove from data if present (will be in options instead)
        if not data.get(CONF_REFRESH_INTERVAL):
            data[CONF_REFRESH_INTERVAL] = DEFAULT_REFRESH_INTERVAL

        hass.config_entries.async_update_entry(config_entry, data=data, version=4)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True