"""Access code and home user management services for Kwikset Smart Locks.

Registers integration-level services for creating, editing, disabling,
enabling, and deleting access codes on Kwikset smart locks, as well as
home user management (invite, update, delete, list).

Access code services accept a device_id (HA device registry ID) to target
a specific lock. Home user services accept a config_entry_id to target
a specific Kwikset home.

Quality Scale:
    Silver: action_exceptions — handlers raise HomeAssistantError
    Gold: exception_translations — all errors have i18n strings
    Platinum: strict_typing — full type annotations, TYPE_CHECKING
"""

from __future__ import annotations

import calendar
import datetime
from functools import reduce
from operator import or_
from typing import TYPE_CHECKING
from typing import Any

import voluptuous as vol
from aiokwikset.access_code import AccessCodeSchedule
from aiokwikset.access_code import DayOfWeek
from aiokwikset.access_code import ScheduleType
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.core import ServiceResponse
from homeassistant.core import SupportsResponse
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import CONF_HOME_ID
from .const import DOMAIN
from .const import LOGGER
from .const import SCHEDULE_TYPE_ALL_DAY
from .const import SCHEDULE_TYPE_DATE_RANGE
from .const import SCHEDULE_TYPE_ONE_TIME_24_HOUR
from .const import SCHEDULE_TYPE_ONE_TIME_UNLIMITED
from .const import SCHEDULE_TYPE_WEEKLY
from .const import SERVICE_CREATE_ACCESS_CODE
from .const import SERVICE_DELETE_ACCESS_CODE
from .const import SERVICE_DELETE_ALL_ACCESS_CODES
from .const import SERVICE_DELETE_USER
from .const import SERVICE_DISABLE_ACCESS_CODE
from .const import SERVICE_EDIT_ACCESS_CODE
from .const import SERVICE_ENABLE_ACCESS_CODE
from .const import SERVICE_INVITE_USER
from .const import SERVICE_LIST_ACCESS_CODES
from .const import SERVICE_LIST_USERS
from .const import SERVICE_UPDATE_USER

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# =============================================================================
# Constants
# =============================================================================

SCHEDULE_TYPE_MAP: dict[str, ScheduleType] = {
    SCHEDULE_TYPE_ALL_DAY: ScheduleType.ALL_DAY,
    SCHEDULE_TYPE_DATE_RANGE: ScheduleType.DATE_RANGE,
    SCHEDULE_TYPE_WEEKLY: ScheduleType.WEEKLY,
    SCHEDULE_TYPE_ONE_TIME_UNLIMITED: ScheduleType.ONE_TIME_UNLIMITED,
    SCHEDULE_TYPE_ONE_TIME_24_HOUR: ScheduleType.ONE_TIME_24_HOUR,
}

DAY_OF_WEEK_MAP: dict[str, DayOfWeek] = {
    "sunday": DayOfWeek.SUNDAY,
    "monday": DayOfWeek.MONDAY,
    "tuesday": DayOfWeek.TUESDAY,
    "wednesday": DayOfWeek.WEDNESDAY,
    "thursday": DayOfWeek.THURSDAY,
    "friday": DayOfWeek.FRIDAY,
    "saturday": DayOfWeek.SATURDAY,
}

_VALID_SCHEDULE_TYPES: list[str] = list(SCHEDULE_TYPE_MAP.keys())
_VALID_DAYS: list[str] = list(DAY_OF_WEEK_MAP.keys())

# =============================================================================
# Voluptuous Schemas
# =============================================================================

_SCHEDULE_FIELDS: dict[vol.Optional, Any] = {
    vol.Optional("start_time"): cv.time,
    vol.Optional("end_time"): cv.time,
    vol.Optional("start_date"): cv.date,
    vol.Optional("end_date"): cv.date,
    vol.Optional("days_of_week"): vol.All(
        cv.ensure_list,
        [vol.In(_VALID_DAYS)],
    ),
}

SERVICE_CREATE_ACCESS_CODE_SCHEMA = vol.Schema(
    {  # type: ignore[misc]
        vol.Required("device_id"): cv.string,
        vol.Required("code"): vol.All(cv.string, vol.Match(r"^\d{4,8}$")),
        vol.Required("name"): cv.string,
        vol.Required("schedule_type"): vol.In(_VALID_SCHEDULE_TYPES),
        vol.Optional("slot", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        **_SCHEDULE_FIELDS,
    }
)

SERVICE_EDIT_ACCESS_CODE_SCHEMA = vol.Schema(
    {  # type: ignore[misc]
        vol.Required("device_id"): cv.string,
        vol.Required("code"): vol.All(cv.string, vol.Match(r"^\d{4,8}$")),
        vol.Required("name"): cv.string,
        vol.Required("schedule_type"): vol.In(_VALID_SCHEDULE_TYPES),
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        **_SCHEDULE_FIELDS,
    }
)

SERVICE_DISABLE_ACCESS_CODE_SCHEMA = vol.Schema(
    {  # type: ignore[misc]
        vol.Required("device_id"): cv.string,
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("code"): vol.All(cv.string, vol.Match(r"^\d{4,8}$")),
        vol.Optional("name"): cv.string,
        vol.Optional("schedule_type"): vol.In(_VALID_SCHEDULE_TYPES),
        **_SCHEDULE_FIELDS,
    }
)

SERVICE_ENABLE_ACCESS_CODE_SCHEMA = vol.Schema(
    {  # type: ignore[misc]
        vol.Required("device_id"): cv.string,
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("code"): vol.All(cv.string, vol.Match(r"^\d{4,8}$")),
        vol.Optional("name"): cv.string,
        vol.Optional("schedule_type"): vol.In(_VALID_SCHEDULE_TYPES),
        **_SCHEDULE_FIELDS,
    }
)

SERVICE_DELETE_ACCESS_CODE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    }
)

SERVICE_DELETE_ALL_ACCESS_CODES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
    }
)

# Valid abbreviated day names for home user weekly schedule
_VALID_SHORT_DAYS: list[str] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Home user management schemas (config-entry-scoped)
SERVICE_INVITE_USER_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("email"): cv.string,
        vol.Required("access_level"): vol.In(["Member", "Admin"]),
        vol.Required("nickname"): cv.string,
        vol.Required("allowed_devices"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("access_time_type"): vol.In(["date_range", "weekly"]),
        vol.Optional("start_date"): cv.date,
        vol.Optional("end_date"): cv.date,
        vol.Optional("start_time"): cv.time,
        vol.Optional("end_time"): cv.time,
        vol.Optional("days"): vol.All(cv.ensure_list, [vol.In(_VALID_SHORT_DAYS)]),
    }
)

SERVICE_UPDATE_USER_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("email"): cv.string,
        vol.Required("access_level"): vol.In(["Member", "Admin"]),
        vol.Required("allowed_devices"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("access_time_type"): vol.In(["date_range", "weekly"]),
        vol.Optional("start_date"): cv.date,
        vol.Optional("end_date"): cv.date,
        vol.Optional("start_time"): cv.time,
        vol.Optional("end_time"): cv.time,
        vol.Optional("days"): vol.All(cv.ensure_list, [vol.In(_VALID_SHORT_DAYS)]),
    }
)

SERVICE_DELETE_USER_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("email"): cv.string,
    }
)

SERVICE_LIST_USERS_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
    }
)


# =============================================================================
# Helper Functions
# =============================================================================


def _resolve_coordinator(
    hass: HomeAssistant,
    device_id: str,
) -> KwiksetDeviceDataUpdateCoordinator:
    """Resolve HA device registry ID to Kwikset coordinator.

    Args:
        hass: Home Assistant instance.
        device_id: HA device registry ID.

    Returns:
        The coordinator for the specified device.

    Raises:
        HomeAssistantError: If the device is not found or not a Kwikset device.

    """
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if device_entry is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Extract Kwikset device ID from device identifiers
    kwikset_device_id: str | None = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:
            kwikset_device_id = identifier[1]
            break

    if kwikset_device_id is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Find the coordinator across all config entries
    for entry_id in device_entry.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is not None
            and entry.domain == DOMAIN
            and hasattr(entry, "runtime_data")
            and entry.runtime_data is not None
        ):
            coordinator = entry.runtime_data.devices.get(kwikset_device_id)
            if coordinator is not None:
                return coordinator

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
    )


def _resolve_config_entry(
    hass: HomeAssistant,
    config_entry_id: str,
) -> KwiksetConfigEntry:
    """Resolve config entry ID to a loaded Kwikset config entry.

    Args:
        hass: Home Assistant instance.
        config_entry_id: HA config entry ID.

    Returns:
        The loaded Kwikset config entry.

    Raises:
        HomeAssistantError: If the entry is not found or not loaded.

    """
    entry = hass.config_entries.async_get_entry(config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
        )
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )
    return entry


def _resolve_kwikset_device_ids(
    hass: HomeAssistant,
    ha_device_ids: list[str],
) -> list[str]:
    """Resolve HA device registry IDs to Kwikset device IDs.

    Args:
        hass: Home Assistant instance.
        ha_device_ids: List of HA device registry IDs.

    Returns:
        List of Kwikset device IDs (e.g. ["1041d5b8b6eb2ea917"]).

    Raises:
        HomeAssistantError: If any device cannot be resolved.

    """
    device_registry = dr.async_get(hass)
    kwikset_ids: list[str] = []
    for ha_id in ha_device_ids:
        device_entry = device_registry.async_get(ha_id)
        if device_entry is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )
        kwikset_id: str | None = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                kwikset_id = identifier[1]
                break
        if kwikset_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_kwikset",
            )
        kwikset_ids.append(kwikset_id)
    return kwikset_ids


def _build_home_user_access_time(data: dict[str, Any]) -> dict[str, Any] | None:
    """Build an access_time dict for home user invite/update calls.

    Supports DATE_RANGE (schedule) and WEEKLY (repeat) access time types.

    Args:
        data: Service call data dictionary.

    Returns:
        An access_time dict for the API, or None if no schedule requested.

    """
    access_time_type = data.get("access_time_type")
    if access_time_type is None:
        return None

    if access_time_type == "date_range":
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if not start_date or not end_date:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="missing_date_range_fields",
            )
        start_epoch = str(int(calendar.timegm(start_date.timetuple())))
        end_epoch = str(int(calendar.timegm(end_date.timetuple())))
        return {
            "accesstimetype": "DATE_RANGE",
            "startdate": start_epoch,
            "enddate": end_epoch,
        }

    if access_time_type == "weekly":
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        days = data.get("days")
        if not start_time or not end_time or not days:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="missing_weekly_fields",
            )
        # Convert time objects to epoch using a reference date
        ref_date = datetime.date(2026, 1, 1)
        start_dt = datetime.datetime.combine(ref_date, start_time)
        end_dt = datetime.datetime.combine(ref_date, end_time)
        start_epoch = str(int(calendar.timegm(start_dt.timetuple())))
        end_epoch = str(int(calendar.timegm(end_dt.timetuple())))
        return {
            "accesstimetype": "WEEKLY",
            "starttime": start_epoch,
            "endtime": end_epoch,
            "days": days,
        }

    return None


def _build_schedule(data: dict[str, Any]) -> AccessCodeSchedule:
    """Build an AccessCodeSchedule from service call data.

    Args:
        data: Service call data dictionary.

    Returns:
        Configured AccessCodeSchedule instance.

    Raises:
        HomeAssistantError: If required schedule parameters are missing.

    """
    schedule_type = SCHEDULE_TYPE_MAP[data["schedule_type"]]

    kwargs: dict[str, Any] = {"schedule_type": schedule_type}

    # Parse time fields (cv.time returns datetime.time objects)
    start_time: datetime.time | None = data.get("start_time")
    end_time: datetime.time | None = data.get("end_time")

    if start_time is not None:
        kwargs["start_hour"] = start_time.hour
        kwargs["start_minute"] = start_time.minute

    if end_time is not None:
        kwargs["end_hour"] = end_time.hour
        kwargs["end_minute"] = end_time.minute

    # Parse date fields (cv.date returns datetime.date objects)
    start_date: datetime.date | None = data.get("start_date")
    end_date: datetime.date | None = data.get("end_date")

    if start_date is not None:
        kwargs["start_month"] = start_date.month
        kwargs["start_day"] = start_date.day
        kwargs["start_year"] = start_date.year

    if end_date is not None:
        kwargs["end_month"] = end_date.month
        kwargs["end_day"] = end_date.day
        kwargs["end_year"] = end_date.year

    # Parse days of week
    days_list: list[str] | None = data.get("days_of_week")
    if days_list:
        day_flags = [DAY_OF_WEEK_MAP[day] for day in days_list]
        kwargs["days_of_week"] = reduce(or_, day_flags)

    # Validate schedule-specific requirements
    if schedule_type == ScheduleType.DATE_RANGE and (
        start_date is None or end_date is None
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_schedule_params",
        )

    if schedule_type == ScheduleType.WEEKLY and not days_list:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_schedule_params",
        )

    return AccessCodeSchedule(**kwargs)


def _resolve_stored_code_params(
    coordinator: KwiksetDeviceDataUpdateCoordinator,
    data: dict[str, Any],
) -> tuple[str, str, AccessCodeSchedule]:
    """Resolve code, name, and schedule from stored data with optional overrides.

    For disable/enable calls that only provide device_id + slot, this looks up
    the stored access code metadata. Any fields explicitly provided in the
    service call data override the stored values.

    Args:
        coordinator: Device coordinator with access code store.
        data: Service call data (slot required; code/name/schedule_type optional).

    Returns:
        Tuple of (code, name, schedule).

    Raises:
        HomeAssistantError: If the code cannot be resolved
            (not tracked and not provided).

    """
    slot = data["slot"]
    tracked = coordinator.get_tracked_code(slot)

    # Resolve code: override > stored > error
    code: str | None = data.get("code")
    if code is None and tracked is not None:
        code = tracked.get("code", "")
    if not code:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="access_code_not_tracked",
            translation_placeholders={"slot": str(slot)},
        )

    # Resolve name: override > stored > fallback
    name: str = data.get("name") or (tracked.get("name", "") if tracked else "")
    if not name:
        name = f"Code {slot}"

    # Resolve schedule_type: override > stored > fallback to all_day
    schedule_type_str: str = data.get("schedule_type") or (
        tracked.get("schedule_type", "all_day") if tracked else "all_day"
    )

    # Build schedule data dict for _build_schedule
    schedule_data: dict[str, Any] = {**data, "schedule_type": schedule_type_str}
    schedule = _build_schedule(schedule_data)

    return code, name, schedule


# =============================================================================
# Service Handlers
# =============================================================================


async def async_handle_create_access_code(call: ServiceCall) -> ServiceResponse:
    """Handle create_access_code service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    code = data["code"]
    name = data["name"]
    slot = data.get("slot", 0)
    schedule = _build_schedule(data)

    try:
        result = await coordinator.create_access_code(
            code=code,
            name=name,
            schedule=schedule,
            slot=slot,
        )
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="create_access_code_failed",
        ) from err

    LOGGER.info(
        "Access code '%s' created on %s (token=%s)",
        name,
        coordinator.device_name,
        result.token,
    )

    # Persist access code metadata to tracking store
    await coordinator.async_track_access_code(
        slot=slot,
        name=name,
        code=code,
        schedule_type=data["schedule_type"],
        enabled=True,
    )

    return {
        "token": result.token,
        "slot": slot,
        "name": name,
    }


async def async_handle_edit_access_code(call: ServiceCall) -> ServiceResponse:
    """Handle edit_access_code service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    code = data["code"]
    name = data["name"]
    slot = data["slot"]
    schedule = _build_schedule(data)

    try:
        result = await coordinator.edit_access_code(
            code=code,
            name=name,
            schedule=schedule,
            slot=slot,
        )
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="edit_access_code_failed",
        ) from err

    LOGGER.info(
        "Access code '%s' edited on %s slot %d",
        name,
        coordinator.device_name,
        slot,
    )

    # Persist updated access code metadata
    await coordinator.async_track_access_code(
        slot=slot,
        name=name,
        code=code,
        schedule_type=data["schedule_type"],
        enabled=True,
    )

    return {
        "token": result.token,
        "slot": slot,
        "name": name,
    }


async def async_handle_disable_access_code(call: ServiceCall) -> ServiceResponse:
    """Handle disable_access_code service call.

    Only device_id and slot are required. If the code was created through HA,
    the stored code/name/schedule are used automatically. Any field can be
    overridden by providing it explicitly in the service call.
    """
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    slot = data["slot"]
    code, name, schedule = _resolve_stored_code_params(coordinator, data)

    try:
        result = await coordinator.disable_access_code(
            code=code,
            name=name,
            schedule=schedule,
            slot=slot,
        )
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="disable_access_code_failed",
        ) from err

    LOGGER.info(
        "Access code slot %d disabled on %s",
        slot,
        coordinator.device_name,
    )

    # Update tracking store
    await coordinator.async_update_access_code_enabled(slot=slot, enabled=False)

    return {
        "token": result.token,
        "slot": slot,
        "name": name,
    }


async def async_handle_enable_access_code(call: ServiceCall) -> ServiceResponse:
    """Handle enable_access_code service call.

    Only device_id and slot are required. If the code was created through HA,
    the stored code/name/schedule are used automatically. Any field can be
    overridden by providing it explicitly in the service call.
    """
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    slot = data["slot"]
    code, name, schedule = _resolve_stored_code_params(coordinator, data)

    try:
        result = await coordinator.enable_access_code(
            code=code,
            name=name,
            schedule=schedule,
            slot=slot,
        )
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="enable_access_code_failed",
        ) from err

    LOGGER.info(
        "Access code slot %d enabled on %s",
        slot,
        coordinator.device_name,
    )

    # Update tracking store
    await coordinator.async_update_access_code_enabled(slot=slot, enabled=True)

    return {
        "token": result.token,
        "slot": slot,
        "name": name,
    }


async def async_handle_delete_access_code(call: ServiceCall) -> ServiceResponse:
    """Handle delete_access_code service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    slot = data["slot"]

    # Enforce minimum 1 access code per device
    if coordinator.total_access_codes <= 1:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_delete_last_access_code",
        )

    try:
        await coordinator.delete_access_code(slot=slot)
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="delete_access_code_failed",
        ) from err

    LOGGER.info(
        "Access code slot %d deleted on %s",
        slot,
        coordinator.device_name,
    )

    # Remove from tracking store
    await coordinator.async_remove_access_code(slot=slot)

    return {"slot": slot}


async def async_handle_delete_all_access_codes(call: ServiceCall) -> ServiceResponse:
    """Handle delete_all_access_codes service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    _resolve_coordinator(hass, device_id)

    # Always blocked — deleting all codes would violate the minimum-1 rule
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="cannot_delete_all_access_codes",
    )


async def async_handle_list_access_codes(call: ServiceCall) -> ServiceResponse:
    """Handle list_access_codes service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    device_id = data["device_id"]
    coordinator = _resolve_coordinator(hass, device_id)

    codes = coordinator.access_codes
    return {
        "access_codes": [
            {
                "slot": entry["slot"],
                "name": entry["name"],
                "schedule_type": entry["schedule_type"],
                "enabled": entry["enabled"],
                "source": entry["source"],
                "created_at": entry.get("created_at"),
                "last_updated": entry.get("last_updated"),
            }
            for entry in sorted(codes.values(), key=lambda e: e["slot"])
        ],
        "total": len(codes),
    }


SERVICE_LIST_ACCESS_CODES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
    }
)


# =============================================================================
# Home User Management Handlers
# =============================================================================


async def _async_refresh_home_users(entry: KwiksetConfigEntry) -> None:
    """Refresh the cached home user list after a mutation."""
    try:
        entry.runtime_data.home_users = (
            await entry.runtime_data.client.home_user.get_users(  # type: ignore[attr-defined]
                entry.data[CONF_HOME_ID]
            )
        )
    except Exception:
        LOGGER.debug("Failed to refresh home users after mutation", exc_info=True)

    # Trigger coordinator updates so sensor entities refresh
    for coordinator in entry.runtime_data.devices.values():
        coordinator.async_set_updated_data(coordinator.data)


async def async_handle_invite_user(call: ServiceCall) -> ServiceResponse:
    """Handle invite_user service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    entry = _resolve_config_entry(hass, data["config_entry_id"])
    home_id = entry.data[CONF_HOME_ID]
    client = entry.runtime_data.client

    # Resolve HA device registry IDs to Kwikset device IDs
    kwikset_device_ids = _resolve_kwikset_device_ids(hass, data["allowed_devices"])

    # Build access_time if schedule/repeat provided
    access_time = _build_home_user_access_time(data)

    try:
        await client.home_user.invite_user(  # type: ignore[attr-defined]
            home_id,
            data["email"],
            data["access_level"],
            data["nickname"],
            kwikset_device_ids,
            access_time=access_time,
        )
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invite_user_failed",
        ) from err

    # Refresh home users cache
    await _async_refresh_home_users(entry)

    LOGGER.info("Invited user %s to home %s", data["email"], home_id)
    return {"email": data["email"], "access_level": data["access_level"]}


async def async_handle_update_user(call: ServiceCall) -> ServiceResponse:
    """Handle update_user service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    entry = _resolve_config_entry(hass, data["config_entry_id"])
    home_id = entry.data[CONF_HOME_ID]
    client = entry.runtime_data.client

    # Resolve HA device registry IDs to Kwikset device IDs
    kwikset_device_ids = _resolve_kwikset_device_ids(hass, data["allowed_devices"])

    # Build access_time if schedule/repeat provided
    access_time = _build_home_user_access_time(data)

    try:
        await client.home_user.update_user(  # type: ignore[attr-defined]
            home_id,
            data["email"],
            data["access_level"],
            kwikset_device_ids,
            access_time=access_time,
        )
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="update_user_failed",
        ) from err

    # Refresh home users cache
    await _async_refresh_home_users(entry)

    LOGGER.info("Updated user %s in home %s", data["email"], home_id)
    return {"email": data["email"], "access_level": data["access_level"]}


async def async_handle_delete_user(call: ServiceCall) -> ServiceResponse:
    """Handle delete_user service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    entry = _resolve_config_entry(hass, data["config_entry_id"])
    home_id = entry.data[CONF_HOME_ID]
    client = entry.runtime_data.client

    try:
        await client.home_user.delete_user(home_id, data["email"])  # type: ignore[attr-defined]
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="delete_user_failed",
        ) from err

    # Refresh home users cache
    await _async_refresh_home_users(entry)

    LOGGER.info("Deleted user %s from home %s", data["email"], home_id)
    return {"email": data["email"]}


async def async_handle_list_users(call: ServiceCall) -> ServiceResponse:
    """Handle list_users service call."""
    hass: HomeAssistant = call.hass
    data = call.data
    entry = _resolve_config_entry(hass, data["config_entry_id"])
    home_id = entry.data[CONF_HOME_ID]
    client = entry.runtime_data.client

    try:
        users = await client.home_user.get_users(home_id)  # type: ignore[attr-defined]
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="list_users_failed",
        ) from err

    return {
        "users": [
            {
                "name": u.get("sharedwithname", ""),
                "email": u.get("email", ""),
                "access_level": u.get("useraccesslevel", ""),
            }
            for u in users
        ],
        "total": len(users),
    }


# =============================================================================
# Service Registration
# =============================================================================

_SERVICE_HANDLERS: list[tuple[str, vol.Schema, Any, SupportsResponse]] = [
    (
        SERVICE_CREATE_ACCESS_CODE,
        SERVICE_CREATE_ACCESS_CODE_SCHEMA,
        async_handle_create_access_code,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_EDIT_ACCESS_CODE,
        SERVICE_EDIT_ACCESS_CODE_SCHEMA,
        async_handle_edit_access_code,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_DISABLE_ACCESS_CODE,
        SERVICE_DISABLE_ACCESS_CODE_SCHEMA,
        async_handle_disable_access_code,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_ENABLE_ACCESS_CODE,
        SERVICE_ENABLE_ACCESS_CODE_SCHEMA,
        async_handle_enable_access_code,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_DELETE_ACCESS_CODE,
        SERVICE_DELETE_ACCESS_CODE_SCHEMA,
        async_handle_delete_access_code,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_DELETE_ALL_ACCESS_CODES,
        SERVICE_DELETE_ALL_ACCESS_CODES_SCHEMA,
        async_handle_delete_all_access_codes,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_LIST_ACCESS_CODES,
        SERVICE_LIST_ACCESS_CODES_SCHEMA,
        async_handle_list_access_codes,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_INVITE_USER,
        SERVICE_INVITE_USER_SCHEMA,
        async_handle_invite_user,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_UPDATE_USER,
        SERVICE_UPDATE_USER_SCHEMA,
        async_handle_update_user,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_DELETE_USER,
        SERVICE_DELETE_USER_SCHEMA,
        async_handle_delete_user,
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_LIST_USERS,
        SERVICE_LIST_USERS_SCHEMA,
        async_handle_list_users,
        SupportsResponse.ONLY,
    ),
]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register access code and home user management services.

    Only registers services once, even if multiple config entries exist.
    """
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_ACCESS_CODE):
        return

    for service_name, schema, handler, response_type in _SERVICE_HANDLERS:
        hass.services.async_register(
            DOMAIN,
            service_name,
            handler,
            schema=schema,
            supports_response=response_type,
        )

    LOGGER.debug("Access code and home user services registered")


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister access code and home user management services.

    Should only be called when the last config entry is unloaded.
    """
    for service_name, _, _, _ in _SERVICE_HANDLERS:
        hass.services.async_remove(DOMAIN, service_name)

    LOGGER.debug("Access code and home user services unregistered")
