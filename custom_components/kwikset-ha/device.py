"""Kwikset device object"""
import asyncio
from datetime import timedelta
from typing import Any, TypedDict

from aiokwikset.api import API, Unauthenticated
from aiokwikset.errors import RequestError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN as KWIKSET_DOMAIN, LOGGER


class KwiksetDeviceData(TypedDict, total=False):
    """Type for coordinator data."""
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
    """Kwikset device data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: API,
        device_id: str,
        device_name: str,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{KWIKSET_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.api_client = api_client
        self.device_id = device_id
        self._device_name = device_name
        self._manufacturer = "Kwikset"
        self._device_info: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        """Set up the coordinator.
        
        This is called once during async_config_entry_first_refresh.
        Load initial device information here.
        """
        try:
            self._device_info = await self.api_client.device.get_device_info(
                self.device_id
            )
            LOGGER.debug("Initial Kwikset device data loaded: %s", self._device_info)
        except Unauthenticated as error:
            raise ConfigEntryAuthFailed(
                "Authentication failed during initial device setup"
            ) from error
        except RequestError as error:
            raise UpdateFailed(f"Error fetching initial device data: {error}") from error

    async def _async_update_data(self) -> KwiksetDeviceData:
        """Fetch data from API endpoint.
        
        This is called automatically by the coordinator at the configured interval.
        """
        try:
            # Fetch updated device information
            device_info = await self.api_client.device.get_device_info(self.device_id)
            LOGGER.debug("Kwikset device data updated: %s", device_info)
            
            # Store for property access
            self._device_info = device_info
            
            # Parse and structure the data
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
        except Unauthenticated as error:
            raise ConfigEntryAuthFailed(
                "Authentication failed, credentials need to be re-entered"
            ) from error
        except RequestError as error:
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    @staticmethod
    def _parse_bool(value: Any) -> bool | None:
        """Parse boolean value from API response."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        # Handle string/int representations
        return str(value).lower() in ("true", "1", "yes", "on")

    @property
    def id(self) -> str:
        """Return device id"""
        return self.device_id

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_name

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device"""
        return self._manufacturer

    @property
    def model(self) -> str:
        """Return model for device"""
        if self.data:
            return self.data.get("model_number", "Unknown")
        return self._device_info.get("modelnumber", "Unknown")

    @property
    def battery_percentage(self) -> int | None:
        """Return device battery percentage"""
        if self.data:
            return self.data.get("battery_percentage")
        return self._device_info.get("batterypercentage")

    @property
    def firmware_version(self) -> str:
        """Return the firmware version for the device."""
        if self.data:
            return self.data.get("firmware_version", "Unknown")
        return self._device_info.get("firmwarebundleversion", "Unknown")

    @property
    def serial_number(self) -> str:
        """Return the serial number for the device."""
        if self.data:
            return self.data.get("serial_number", "Unknown")
        return self._device_info.get("serialnumber", "Unknown")

    @property
    def status(self) -> str:
        """Return the status of the device"""
        if self.data:
            return self.data.get("door_status", "Unknown")
        return self._device_info.get("doorstatus", "Unknown")

    @property
    def led_status(self) -> bool | None:
        """Return the LED status"""
        if self.data:
            return self.data.get("led_status")
        return self._parse_bool(self._device_info.get("ledstatus"))

    @property
    def audio_status(self) -> bool | None:
        """Return the audio status"""
        if self.data:
            return self.data.get("audio_status")
        return self._parse_bool(self._device_info.get("audiostatus"))

    @property
    def secure_screen_status(self) -> bool | None:
        """Return the secure screen status"""
        if self.data:
            return self.data.get("secure_screen_status")
        return self._parse_bool(self._device_info.get("securescreenstatus"))

    async def lock(self) -> None:
        """Lock the device."""
        try:
            user_info = await self.api_client.user.get_info()
            await self.api_client.device.lock_device(self._device_info, user_info)
            LOGGER.debug("The lock was locked successfully")
            # Request immediate refresh to update state
            await self.async_request_refresh()
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed while locking device"
            ) from err

    async def unlock(self) -> None:
        """Unlock the device."""
        try:
            user_info = await self.api_client.user.get_info()
            await self.api_client.device.unlock_device(self._device_info, user_info)
            LOGGER.debug("The lock was unlocked successfully")
            # Request immediate refresh to update state
            await self.async_request_refresh()
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed while unlocking device"
            ) from err

    async def set_led(self, status: bool) -> None:
        """Set the LED status."""
        try:
            # Convert boolean to string "true" or "false" for API
            status_str = "true" if status else "false"
            await self.api_client.device.set_ledstatus(self._device_info, status_str)
            LOGGER.debug("The lock LED status was set to %s successfully", status_str)
            await self.async_request_refresh()
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed while setting LED status"
            ) from err

    async def set_audio(self, status: bool) -> None:
        """Set the audio status."""
        try:
            # Convert boolean to string "true" or "false" for API
            status_str = "true" if status else "false"
            await self.api_client.device.set_audiostatus(self._device_info, status_str)
            LOGGER.debug("The lock audio status was set to %s successfully", status_str)
            await self.async_request_refresh()
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed while setting audio status"
            ) from err

    async def set_secure_screen(self, status: bool) -> None:
        """Set the secure screen status."""
        try:
            # Convert boolean to string "true" or "false" for API
            status_str = "true" if status else "false"
            await self.api_client.device.set_securescreenstatus(self._device_info, status_str)
            LOGGER.debug("The lock secure screen was set to %s successfully", status_str)
            await self.async_request_refresh()
        except Unauthenticated as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed while setting secure screen status"
            ) from err