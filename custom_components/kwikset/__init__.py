"""Kwikset Smart Locks integration.

Uses DataUpdateCoordinator pattern with one coordinator per lock device.
Supports dynamic device discovery and proactive token refresh.

Data Flow:
    Kwikset Cloud API → aiokwikset → Coordinator → Entity platforms
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from typing import Any

from aiokwikset import API
from aiokwikset.errors import ConnectionError as KwiksetConnectionError
from aiokwikset.errors import RequestError
from aiokwikset.errors import TokenExpiredError
from aiokwikset.errors import Unauthenticated
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_ACCESS_TOKEN
from .const import CONF_HOME_ID
from .const import CONF_ID_TOKEN
from .const import CONF_REFRESH_INTERVAL
from .const import CONF_REFRESH_TOKEN
from .const import CONF_STORED_PASSWORD
from .const import DEFAULT_REFRESH_INTERVAL
from .const import DOMAIN
from .const import LOGGER
from .const import MAX_REFRESH_INTERVAL
from .const import MIN_REFRESH_INTERVAL
from .device import KwiksetDeviceDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR, Platform.SWITCH]
DEVICE_DISCOVERY_INTERVAL = timedelta(minutes=5)


@dataclass
class KwiksetRuntimeData:
    """Runtime data for the Kwikset integration.

    Attributes:
        client: Authenticated API client instance.
        devices: Device ID to coordinator mapping.
        known_devices: Tracked device IDs for stale device detection.
        cancel_device_discovery: Cancellation callback for discovery timer.

    """

    client: API
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = field(default_factory=dict)
    known_devices: set[str] = field(default_factory=set)
    cancel_device_discovery: Callable[[], None] | None = None


# Type alias for typed ConfigEntry access (PEP 695)
type KwiksetConfigEntry = ConfigEntry[KwiksetRuntimeData]

__all__ = ["KwiksetConfigEntry", "KwiksetRuntimeData"]


# =============================================================================
# Helper Functions
# =============================================================================


def _get_update_interval(entry: KwiksetConfigEntry) -> int:
    """Get polling interval from entry options with fallback to default."""
    interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
    return max(MIN_REFRESH_INTERVAL, min(interval, MAX_REFRESH_INTERVAL))


def _create_auth_issue(hass: HomeAssistant, entry: KwiksetConfigEntry) -> None:
    """Create a repair issue for authentication failure."""
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


async def _async_update_tokens(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    id_token: str,
    access_token: str,
    refresh_token: str,
) -> None:
    """Update config entry with new tokens.

    This is called by the aiokwikset library when tokens are refreshed.

    Args:
        hass: Home Assistant instance.
        entry: Config entry with stored tokens.
        id_token: New ID token.
        access_token: New access token.
        refresh_token: New refresh token.

    """
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_ID_TOKEN: id_token,
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: refresh_token,
        },
    )
    LOGGER.debug("Tokens refreshed and saved to config entry")


def _create_coordinator(
    hass: HomeAssistant,
    client: API,
    device: dict[str, Any],
    update_interval: int,
    entry: KwiksetConfigEntry,
) -> KwiksetDeviceDataUpdateCoordinator:
    """Create a coordinator for a device.

    Args:
        hass: Home Assistant instance.
        client: API client for API calls.
        device: Device data from API.
        update_interval: Polling interval in seconds.
        entry: Config entry for the integration.

    Returns:
        Configured coordinator for the device.

    """
    return KwiksetDeviceDataUpdateCoordinator(
        hass,
        api_client=client,
        device_id=device["deviceid"],
        device_name=device["devicename"],
        update_interval=update_interval,
        config_entry=entry,
    )


async def _build_device_coordinators(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    client: API,
    api_devices: list[dict[str, Any]],
) -> dict[str, KwiksetDeviceDataUpdateCoordinator]:
    """Build coordinators for all devices and perform first refresh.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for the integration.
        client: API client for API calls.
        api_devices: List of device data from API.

    Returns:
        Dictionary mapping device IDs to their coordinators.

    """
    update_interval = _get_update_interval(entry)
    devices: dict[str, KwiksetDeviceDataUpdateCoordinator] = {}

    for device in api_devices:
        coordinator = _create_coordinator(hass, client, device, update_interval, entry)
        await coordinator.async_config_entry_first_refresh()
        devices[device["deviceid"]] = coordinator

    return devices


# =============================================================================
# Entry Setup / Unload
# =============================================================================


async def async_setup_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Set up Kwikset from a config entry.

    Authenticates with the API, creates device coordinators, and starts
    periodic device discovery.

    Raises:
        ConfigEntryAuthFailed: If authentication fails.
        ConfigEntryNotReady: If there's a transient connection issue.

    """
    # Get Home Assistant's shared aiohttp session (Platinum: inject-websession)
    websession = async_get_clientsession(hass)

    # Create token update callback bound to this entry
    async def token_update_callback(
        id_token: str, access_token: str, refresh_token: str
    ) -> None:
        """Update tokens when the library refreshes them."""
        await _async_update_tokens(hass, entry, id_token, access_token, refresh_token)

    # Create API client with websession and token callback
    client = API(
        websession=websession,
        token_update_callback=token_update_callback,
    )

    # Authenticate and validate tokens using session restoration
    try:
        await client.async_authenticate_with_tokens(
            id_token=entry.data.get(CONF_ID_TOKEN, ""),
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
        )
        assert client.user is not None  # Set after authentication
        await client.user.get_info()
    except (TokenExpiredError, Unauthenticated) as err:
        LOGGER.warning("Token refresh failed: %s", err)

        # Attempt automatic re-login if password is stored
        stored_password = entry.data.get(CONF_STORED_PASSWORD)
        if stored_password:
            LOGGER.info("Attempting automatic re-login with stored password")
            try:
                await client.async_login(entry.data[CONF_EMAIL], stored_password)
                assert client.user is not None
                await client.user.get_info()
                LOGGER.info("Automatic re-login successful")

                # Persist the new tokens
                await _async_update_tokens(
                    hass,
                    entry,
                    client.id_token,
                    client.access_token,
                    client.refresh_token,
                )
            except Exception as login_err:
                LOGGER.error("Automatic re-login failed: %s", login_err)
                _create_auth_issue(hass, entry)
                raise ConfigEntryAuthFailed(login_err) from login_err
        else:
            _create_auth_issue(hass, entry)
            raise ConfigEntryAuthFailed(err) from err
    except (RequestError, KwiksetConnectionError) as err:
        raise ConfigEntryNotReady from err

    # Fetch devices and create coordinators
    assert client.device is not None  # Set after authentication
    api_devices = await client.device.get_devices(entry.data[CONF_HOME_ID])
    devices = await _build_device_coordinators(hass, entry, client, api_devices)

    # Store runtime data
    entry.runtime_data = KwiksetRuntimeData(
        client=client,
        devices=devices,
        known_devices=set(devices.keys()),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register listeners
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    async def _async_check_devices(_now) -> None:
        """Periodically check for new or removed devices."""
        await _async_update_devices(hass, entry)

    entry.runtime_data.cancel_device_discovery = async_track_time_interval(
        hass,
        _async_check_devices,
        DEVICE_DISCOVERY_INTERVAL,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KwiksetConfigEntry) -> bool:
    """Unload a config entry and clean up resources."""
    if entry.runtime_data.cancel_device_discovery:
        entry.runtime_data.cancel_device_discovery()
        entry.runtime_data.cancel_device_discovery = None

    # Close the API client to cleanup resources
    if hasattr(entry.runtime_data.client, "async_close"):
        await entry.runtime_data.client.async_close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# =============================================================================
# Device Discovery
# =============================================================================


async def _async_add_new_devices(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    new_device_ids: set[str],
    api_devices: list[dict[str, Any]],
) -> None:
    """Create coordinators for newly discovered devices.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for the integration.
        new_device_ids: Set of new device IDs to add.
        api_devices: List of all device data from API.

    """
    runtime_data = entry.runtime_data
    update_interval = _get_update_interval(entry)

    for device in api_devices:
        device_id = device["deviceid"]
        if device_id in new_device_ids:
            coordinator = _create_coordinator(
                hass, runtime_data.client, device, update_interval, entry
            )
            await coordinator.async_config_entry_first_refresh()
            runtime_data.devices[device_id] = coordinator
            runtime_data.known_devices.add(device_id)

    # Notify platforms to add entities for new devices
    hass.bus.async_fire(
        f"{DOMAIN}_new_device",
        {"entry_id": entry.entry_id, "device_ids": list(new_device_ids)},
    )


async def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    removed_device_ids: set[str],
) -> None:
    """Remove devices no longer present in the API.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for the integration.
        removed_device_ids: Set of device IDs to remove.

    """
    runtime_data = entry.runtime_data
    device_registry = dr.async_get(hass)

    for device_id in removed_device_ids:
        # Remove from device registry (cascades to entity removal)
        device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
        if device:
            device_registry.async_update_device(
                device_id=device.id,
                remove_config_entry_id=entry.entry_id,
            )
            LOGGER.debug("Removed device %s from registry", device_id)

        # Cleanup runtime data
        runtime_data.devices.pop(device_id, None)
        runtime_data.known_devices.discard(device_id)


async def _async_update_devices(hass: HomeAssistant, entry: KwiksetConfigEntry) -> None:
    """Check for new or removed devices and update accordingly.

    Implements Silver tier (stale_devices) and Gold tier (dynamic_devices).
    """
    runtime_data = entry.runtime_data

    try:
        assert runtime_data.client.device is not None  # Set after authentication
        api_devices = await runtime_data.client.device.get_devices(
            entry.data[CONF_HOME_ID]
        )
        current_device_ids = {device["deviceid"] for device in api_devices}

        # Handle new devices
        new_device_ids = current_device_ids - runtime_data.known_devices
        if new_device_ids:
            LOGGER.info(
                "Discovered %d new device(s): %s", len(new_device_ids), new_device_ids
            )
            await _async_add_new_devices(hass, entry, new_device_ids, api_devices)

        # Handle removed devices
        removed_device_ids = runtime_data.known_devices - current_device_ids
        if removed_device_ids:
            LOGGER.info(
                "Detected %d removed device(s): %s",
                len(removed_device_ids),
                removed_device_ids,
            )
            await _async_remove_stale_devices(hass, entry, removed_device_ids)

    except (
        TokenExpiredError,
        Unauthenticated,
        RequestError,
        KwiksetConnectionError,
    ):
        LOGGER.exception("Error checking for device changes")


# =============================================================================
# Options & Device Removal
# =============================================================================


async def _async_options_updated(
    hass: HomeAssistant, entry: KwiksetConfigEntry
) -> None:
    """Handle options update by applying new polling interval to coordinators."""
    devices = entry.runtime_data.devices
    if not devices:
        return

    new_interval = _get_update_interval(entry)
    new_interval_td = timedelta(seconds=new_interval)

    for coordinator in devices.values():
        if coordinator.update_interval != new_interval_td:
            old_seconds = (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            )
            coordinator.set_update_interval(new_interval_td)
            LOGGER.debug(
                "Updated refresh interval for %s from %s to %s seconds",
                coordinator.device_name,
                old_seconds,
                new_interval,
            )
            await coordinator.async_request_refresh()


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: KwiksetConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow manual device removal from UI.

    Device will be re-added on next discovery if still in Kwikset account.
    """
    return True


# =============================================================================
# Migration
# =============================================================================


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry to current version.

    Migration History:
        v1 → v2: Version bump only.
        v2 → v3: Added CONF_ACCESS_TOKEN field.
        v3 → v4: Moved CONF_REFRESH_INTERVAL to options.
        v4 → v5: Added CONF_ID_TOKEN field for new aiokwikset API.
        v5 → v6: Expanded polling interval range from 15-60s to 30-900s.
    """
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # v1 → v2: Just a version bump
        hass.config_entries.async_update_entry(config_entry, version=2)

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

    if config_entry.version == 4:
        # v4 → v5: Add CONF_ID_TOKEN (use access_token as placeholder until refreshed)
        data = {**config_entry.data}
        if not data.get(CONF_ID_TOKEN):
            # Use empty string as placeholder - will be populated on first token refresh
            data[CONF_ID_TOKEN] = ""
        hass.config_entries.async_update_entry(config_entry, data=data, version=5)

    if config_entry.version == 5:
        # v5 → v6: Increase default polling interval from 30s to 900s
        # Migrate users on the old default (30) to the new default (900)
        # Users with custom intervals keep their values
        options = {**config_entry.options}
        if options.get(CONF_REFRESH_INTERVAL) == 30:
            options[CONF_REFRESH_INTERVAL] = DEFAULT_REFRESH_INTERVAL
        hass.config_entries.async_update_entry(config_entry, options=options, version=6)

    LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
