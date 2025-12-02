"""Kwikset device coordinator module.

DataUpdateCoordinator for Kwikset smart locks. Each device has its own
coordinator handling polling, token refresh, retry logic, and device actions.

Entities use coordinator methods/properties, never the API directly.

Quality Scale:
    Silver: parallel_updates (via platform modules), action_exceptions
    Gold: diagnostics support via data properties
    Platinum: strict_typing, async_dependency (aiokwikset)
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

from aiokwikset.api import API, Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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

# Type variable for generic API call return type
_T = TypeVar("_T")

# API response keys (avoid magic strings throughout the code)
_KEY_DOOR_STATUS = "doorstatus"
_KEY_BATTERY = "batterypercentage"
_KEY_MODEL = "modelnumber"
_KEY_SERIAL = "serialnumber"
_KEY_FIRMWARE = "firmwarebundleversion"
_KEY_LED = "ledstatus"
_KEY_AUDIO = "audiostatus"
_KEY_SECURE_SCREEN = "securescreenstatus"


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

    Centralizes API communication, token refresh, and retry logic.
    Entities use coordinator methods/properties, never the API directly.
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
        self._device_info: dict[str, Any] = {}
        self._token_expiry: float | None = None
        self._parse_token_expiry()

    # -------------------------------------------------------------------------
    # Token Management
    # -------------------------------------------------------------------------

    def _parse_token_expiry(self) -> None:
        """Parse JWT token to extract expiration time."""
        access_token = self.config_entry.data.get(CONF_ACCESS_TOKEN, "")
        parts = access_token.split(".")
        if len(parts) != 3:
            self._token_expiry = None
            return

        try:
            # Decode JWT payload (add base64 padding)
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            token_data = json.loads(base64.urlsafe_b64decode(payload))
            self._token_expiry = float(token_data["exp"])
            LOGGER.debug("Token expiry parsed: %s", self._token_expiry)
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
            # Create repair issue to notify user of authentication expiry
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"auth_expired_{self.config_entry.entry_id}",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="auth_expired",
                translation_placeholders={"entry_title": self.config_entry.title},
            )
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="token_refresh_failed",
            ) from err
        except RequestError as err:
            LOGGER.warning("Token refresh network error: %s", err)

    # -------------------------------------------------------------------------
    # API Call Wrapper
    # -------------------------------------------------------------------------

    async def _api_call_with_retry(
        self,
        api_call: Callable[..., Awaitable[_T]],
        *args: Any,
        **kwargs: Any,
    ) -> _T:
        """Execute API call with retry logic and token refresh."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRY_ATTEMPTS):
            await self._ensure_valid_token()
            try:
                return await api_call(*args, **kwargs)
            except Unauthenticated as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            except RequestError as err:
                last_error = err
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.debug(
                        "API call failed (attempt %d/%d): %s",
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        err,
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_error",
        ) from last_error

    # -------------------------------------------------------------------------
    # Coordinator Lifecycle
    # -------------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Load initial device information."""
        self._device_info = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        LOGGER.debug("Initial device data loaded for %s", self.device_id)

    async def _async_update_data(self) -> KwiksetDeviceData:
        """Fetch current device state."""
        info = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        self._device_info = info

        return KwiksetDeviceData(
            device_info=info,
            door_status=info.get(_KEY_DOOR_STATUS, "Unknown"),
            battery_percentage=info.get(_KEY_BATTERY),
            model_number=info.get(_KEY_MODEL, "Unknown"),
            serial_number=info.get(_KEY_SERIAL, "Unknown"),
            firmware_version=info.get(_KEY_FIRMWARE, "Unknown"),
            led_status=self._parse_bool(info.get(_KEY_LED)),
            audio_status=self._parse_bool(info.get(_KEY_AUDIO)),
            secure_screen_status=self._parse_bool(info.get(_KEY_SECURE_SCREEN)),
        )

    @staticmethod
    def _parse_bool(value: Any) -> bool | None:
        """Parse boolean from API response (handles string 'true'/'false')."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")

    # -------------------------------------------------------------------------
    # Device Properties (for entity.py device_info)
    # -------------------------------------------------------------------------

    def _get_value(self, data_key: str, raw_key: str, default: str = "Unknown") -> Any:
        """Get value from coordinator data or fallback to raw device info."""
        if self.data:
            return self.data.get(data_key, default)
        return self._device_info.get(raw_key, default)

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_name

    @property
    def manufacturer(self) -> str:
        """Return manufacturer (always Kwikset)."""
        return "Kwikset"

    @property
    def model(self) -> str:
        """Return device model."""
        return self._get_value("model_number", _KEY_MODEL)

    @property
    def battery_percentage(self) -> int | None:
        """Return battery percentage."""
        if self.data:
            return self.data.get("battery_percentage")
        return self._device_info.get(_KEY_BATTERY)

    @property
    def firmware_version(self) -> str:
        """Return firmware version."""
        return self._get_value("firmware_version", _KEY_FIRMWARE)

    @property
    def serial_number(self) -> str:
        """Return serial number."""
        return self._get_value("serial_number", _KEY_SERIAL)

    @property
    def status(self) -> str:
        """Return lock status (Locked/Unlocked/Unknown)."""
        return self._get_value("door_status", _KEY_DOOR_STATUS)

    @property
    def led_status(self) -> bool | None:
        """Return LED status."""
        if self.data:
            return self.data.get("led_status")
        return self._parse_bool(self._device_info.get(_KEY_LED))

    @property
    def audio_status(self) -> bool | None:
        """Return audio status."""
        if self.data:
            return self.data.get("audio_status")
        return self._parse_bool(self._device_info.get(_KEY_AUDIO))

    @property
    def secure_screen_status(self) -> bool | None:
        """Return secure screen status."""
        if self.data:
            return self.data.get("secure_screen_status")
        return self._parse_bool(self._device_info.get(_KEY_SECURE_SCREEN))

    # -------------------------------------------------------------------------
    # Device Actions (called by entity platforms)
    # -------------------------------------------------------------------------

    async def _get_user_info(self) -> dict[str, Any]:
        """Get user info required for lock/unlock commands."""
        return await self._api_call_with_retry(self.api_client.user.get_info)

    async def lock(self) -> None:
        """Lock the device."""
        user_info = await self._get_user_info()
        await self._api_call_with_retry(
            self.api_client.device.lock_device,
            self._device_info,
            user_info,
        )
        LOGGER.debug("Lock command sent for %s", self.device_id)
        await self.async_request_refresh()

    async def unlock(self) -> None:
        """Unlock the device."""
        user_info = await self._get_user_info()
        await self._api_call_with_retry(
            self.api_client.device.unlock_device,
            self._device_info,
            user_info,
        )
        LOGGER.debug("Unlock command sent for %s", self.device_id)
        await self.async_request_refresh()

    async def set_led(self, enabled: bool) -> None:
        """Set LED status."""
        await self._api_call_with_retry(
            self.api_client.device.set_ledstatus,
            self._device_info,
            "true" if enabled else "false",
        )
        LOGGER.debug("LED set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()

    async def set_audio(self, enabled: bool) -> None:
        """Set audio status."""
        await self._api_call_with_retry(
            self.api_client.device.set_audiostatus,
            self._device_info,
            "true" if enabled else "false",
        )
        LOGGER.debug("Audio set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()

    async def set_secure_screen(self, enabled: bool) -> None:
        """Set secure screen status."""
        await self._api_call_with_retry(
            self.api_client.device.set_securescreenstatus,
            self._device_info,
            "true" if enabled else "false",
        )
        LOGGER.debug("Secure screen set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()