"""Kwikset device coordinator module.

This module provides the DataUpdateCoordinator for Kwikset smart locks.
Each physical lock device has its own coordinator instance that handles:

    - Periodic polling for device state (configurable 15-60 second interval)
    - Proactive JWT token refresh (5 minutes before expiry)
    - Retry logic for transient API failures
    - Device actions (lock, unlock, set LED/audio/secure screen)

Architecture:
    The coordinator is the single point of contact with the Kwikset API for
    a device. Entities should NEVER call the API directly - they should use
    coordinator methods (lock(), unlock(), set_led(), etc.) and properties.

    This pattern ensures:
        - Consistent retry logic for all operations
        - Proper token refresh before any API call
        - Centralized error handling
        - Rate limiting via PARALLEL_UPDATES

Token Management:
    JWT tokens are parsed to extract expiration time. The coordinator
    proactively refreshes tokens 5 minutes before expiry to prevent
    authentication failures during normal operations. Refreshed tokens
    are saved back to the config entry for persistence across restarts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypedDict

from aiokwikset.api import API, Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    LOGGER,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    TOKEN_REFRESH_BUFFER_SECONDS,
)

if TYPE_CHECKING:
    from . import KwiksetConfigEntry

# Note: PARALLEL_UPDATES is defined in const.py and imported by platform modules
# This coordinator is used by all platforms; rate limiting is enforced at platform level


class KwiksetDeviceData(TypedDict, total=False):
    """Type definition for coordinator data."""

    device_info: dict[str, Any]
    door_status: str
    battery_percentage: int | None
    model_number: str
    serial_number: str
    firmware_version: str
    led_status: bool | None
    audio_status: bool | None
    secure_screen_status: bool | None


class KwiksetDeviceDataUpdateCoordinator(DataUpdateCoordinator[KwiksetDeviceData]):
    """Coordinator for a single Kwikset device.

    Handles all API communication, token refresh, and retry logic.
    Entities should use coordinator methods and properties, never the API directly.
    """

    config_entry: KwiksetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: API,
        device_id: str,
        device_name: str,
        update_interval: int,
        config_entry: KwiksetConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=update_interval),
            config_entry=config_entry,
        )
        self.api_client = api_client
        self.device_id = device_id
        self._device_name = device_name
        self._manufacturer = "Kwikset"
        self._device_info: dict[str, Any] = {}
        self._token_expiry: float | None = None
        self._parse_token_expiry()

    # -------------------------------------------------------------------------
    # Token management
    # -------------------------------------------------------------------------

    def _parse_token_expiry(self) -> None:
        """Parse JWT token to extract expiration time."""
        try:
            access_token = self.config_entry.data.get(CONF_ACCESS_TOKEN, "")
            parts = access_token.split(".")
            if len(parts) != 3:
                return

            # Decode JWT payload with padding
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            token_data = json.loads(base64.urlsafe_b64decode(payload))
            if exp := token_data.get("exp"):
                self._token_expiry = float(exp)
                LOGGER.debug("Token expiry: %s", self._token_expiry)
        except (ValueError, KeyError, json.JSONDecodeError) as err:
            LOGGER.debug("Could not parse token expiry: %s", err)
            self._token_expiry = None

    def _is_token_expiring_soon(self) -> bool:
        """Check if token is expiring within buffer period."""
        if self._token_expiry is None:
            return True
        return time.time() >= (self._token_expiry - TOKEN_REFRESH_BUFFER_SECONDS)

    async def _ensure_valid_token(self) -> None:
        """Refresh token if expiring soon."""
        if not self._is_token_expiring_soon():
            return

        LOGGER.debug("Token expiring soon, refreshing proactively")
        try:
            await self.api_client.async_renew_access_token(
                self.config_entry.data[CONF_ACCESS_TOKEN],
                self.config_entry.data[CONF_REFRESH_TOKEN],
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_ACCESS_TOKEN: self.api_client.access_token,
                    CONF_REFRESH_TOKEN: self.api_client.refresh_token,
                },
            )
            self._parse_token_expiry()
            LOGGER.debug("Token refreshed successfully")
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed("Token refresh failed") from err
        except RequestError as err:
            LOGGER.warning("Token refresh network error: %s", err)

    # -------------------------------------------------------------------------
    # API call wrapper with retry
    # -------------------------------------------------------------------------

    async def _api_call_with_retry(self, api_call, *args, **kwargs) -> Any:
        """Execute API call with retry logic."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                await self._ensure_valid_token()
                return await api_call(*args, **kwargs)
            except Unauthenticated as err:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            except RequestError as err:
                last_error = err
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.debug(
                        "API call failed (attempt %d/%d), retrying: %s",
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        err,
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        raise UpdateFailed(f"API error after {MAX_RETRY_ATTEMPTS} attempts") from last_error

    # -------------------------------------------------------------------------
    # Coordinator lifecycle
    # -------------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Load initial device information."""
        self._device_info = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        LOGGER.debug("Initial device data loaded: %s", self._device_info)

    async def _async_update_data(self) -> KwiksetDeviceData:
        """Fetch current device state."""
        device_info = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        self._device_info = device_info

        return KwiksetDeviceData(
            device_info=device_info,
            door_status=device_info.get("doorstatus", "Unknown"),
            battery_percentage=device_info.get("batterypercentage"),
            model_number=device_info.get("modelnumber", "Unknown"),
            serial_number=device_info.get("serialnumber", "Unknown"),
            firmware_version=device_info.get("firmwarebundleversion", "Unknown"),
            led_status=self._parse_bool(device_info.get("ledstatus")),
            audio_status=self._parse_bool(device_info.get("audiostatus")),
            secure_screen_status=self._parse_bool(device_info.get("securescreenstatus")),
        )

    @staticmethod
    def _parse_bool(value: Any) -> bool | None:
        """Parse boolean from API response."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")

    # -------------------------------------------------------------------------
    # Device properties
    # -------------------------------------------------------------------------

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_name

    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self._manufacturer

    @property
    def model(self) -> str:
        """Return device model."""
        return (self.data or {}).get("model_number") or self._device_info.get(
            "modelnumber", "Unknown"
        )

    @property
    def battery_percentage(self) -> int | None:
        """Return battery percentage."""
        return (self.data or {}).get("battery_percentage") or self._device_info.get(
            "batterypercentage"
        )

    @property
    def firmware_version(self) -> str:
        """Return firmware version."""
        return (self.data or {}).get("firmware_version") or self._device_info.get(
            "firmwarebundleversion", "Unknown"
        )

    @property
    def serial_number(self) -> str:
        """Return serial number."""
        return (self.data or {}).get("serial_number") or self._device_info.get(
            "serialnumber", "Unknown"
        )

    @property
    def status(self) -> str:
        """Return lock status."""
        return (self.data or {}).get("door_status") or self._device_info.get(
            "doorstatus", "Unknown"
        )

    @property
    def led_status(self) -> bool | None:
        """Return LED status."""
        if self.data:
            return self.data.get("led_status")
        return self._parse_bool(self._device_info.get("ledstatus"))

    @property
    def audio_status(self) -> bool | None:
        """Return audio status."""
        if self.data:
            return self.data.get("audio_status")
        return self._parse_bool(self._device_info.get("audiostatus"))

    @property
    def secure_screen_status(self) -> bool | None:
        """Return secure screen status."""
        if self.data:
            return self.data.get("secure_screen_status")
        return self._parse_bool(self._device_info.get("securescreenstatus"))

    # -------------------------------------------------------------------------
    # Device actions
    # -------------------------------------------------------------------------

    async def lock(self) -> None:
        """Lock the device."""
        await self._ensure_valid_token()
        user_info = await self._api_call_with_retry(self.api_client.user.get_info)
        await self._api_call_with_retry(
            self.api_client.device.lock_device,
            self._device_info,
            user_info,
        )
        LOGGER.debug("Lock command successful")
        await self.async_request_refresh()

    async def unlock(self) -> None:
        """Unlock the device."""
        await self._ensure_valid_token()
        user_info = await self._api_call_with_retry(self.api_client.user.get_info)
        await self._api_call_with_retry(
            self.api_client.device.unlock_device,
            self._device_info,
            user_info,
        )
        LOGGER.debug("Unlock command successful")
        await self.async_request_refresh()

    async def set_led(self, status: bool) -> None:
        """Set LED status."""
        await self._ensure_valid_token()
        await self._api_call_with_retry(
            self.api_client.device.set_ledstatus,
            self._device_info,
            "true" if status else "false",
        )
        LOGGER.debug("LED set to %s", status)
        await self.async_request_refresh()

    async def set_audio(self, status: bool) -> None:
        """Set audio status."""
        await self._ensure_valid_token()
        await self._api_call_with_retry(
            self.api_client.device.set_audiostatus,
            self._device_info,
            "true" if status else "false",
        )
        LOGGER.debug("Audio set to %s", status)
        await self.async_request_refresh()

    async def set_secure_screen(self, status: bool) -> None:
        """Set secure screen status."""
        await self._ensure_valid_token()
        await self._api_call_with_retry(
            self.api_client.device.set_securescreenstatus,
            self._device_info,
            "true" if status else "false",
        )
        LOGGER.debug("Secure screen set to %s", status)
        await self.async_request_refresh()