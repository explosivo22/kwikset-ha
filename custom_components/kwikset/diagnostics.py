"""Diagnostics support for Kwikset Smart Locks."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_TOKEN
from .const import CONF_HOME_ID
from .const import CONF_ID_TOKEN
from .const import CONF_REFRESH_TOKEN

if TYPE_CHECKING:
    from . import KwiksetConfigEntry

# Keys to redact from diagnostics
TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_HOME_ID,
    "deviceid",
    "serialnumber",
    "userid",
    "email",
    "firstname",
    "lastname",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KwiksetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    devices_dict = entry.runtime_data.devices

    devices_data = []
    for device_id, coordinator in devices_dict.items():
        device_info = {
            "device_id": device_id,
            "device_name": coordinator.device_name,
            "model": coordinator.model,
            "firmware_version": coordinator.firmware_version,
            "status": coordinator.status,
            "battery_percentage": coordinator.battery_percentage,
            "led_status": coordinator.led_status,
            "audio_status": coordinator.audio_status,
            "secure_screen_status": coordinator.secure_screen_status,
            "last_update_success": coordinator.last_update_success,
        }
        devices_data.append(device_info)

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "devices": async_redact_data(devices_data, TO_REDACT),
        "device_count": len(devices_data),
    }
