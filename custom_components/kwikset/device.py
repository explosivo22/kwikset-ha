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
import json
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict
from typing import TypeVar

from aiokwikset import API
from aiokwikset import AccessCodeResult
from aiokwikset import AccessCodeSchedule
from aiokwikset import MqttCommandType
from aiokwikset import parse_lock_mq_response
from aiokwikset import parse_single_access_code_crc
from aiokwikset.errors import ConnectionError as KwiksetConnectionError
from aiokwikset.errors import RequestError
from aiokwikset.errors import TokenExpiredError
from aiokwikset.errors import Unauthenticated
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .const import HISTORY_FETCH_TIMEOUT_SECONDS
from .const import HISTORY_MAX_RETRY_ATTEMPTS
from .const import LOGGER
from .const import MAX_RETRY_ATTEMPTS
from .const import RETRY_DELAY_SECONDS
from .const import WEBSOCKET_FIELD_DEVICE_STATUS

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

# API response keys for access code fields
_KEY_ACCESS_CODE_CRC = "accesscodecrc"
_KEY_ACCESS_CODE_64 = "accesscodesixtyfour"
_KEY_ACCESS_CODE_8 = "accesscodeeight"
_KEY_ACCESS_CODE_BY_INDEX = "accesscodebyindex"
_KEY_LOCK_MQ_RESPONSE = "lockmqresponse"
_KEY_SINGLE_ACCESS_CODE_CRC = "singleAccessCodeCrc"


class AccessCodeEntry(TypedDict):
    """Metadata for a single access code slot."""

    slot: int
    name: str
    code: str
    schedule_type: str
    enabled: bool
    source: str
    created_at: str | None
    last_updated: str | None


class AccessCodeSlotData(TypedDict):
    """Raw slot occupancy data parsed from device info fields."""

    slot: int
    occupied: bool
    crc_token: str | None
    raw_data: str | None


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
    history_events: list[dict[str, Any]]


class KwiksetDeviceDataUpdateCoordinator(DataUpdateCoordinator[KwiksetDeviceData]):
    """Coordinator for a single Kwikset device.

    Centralizes API communication and retry logic.
    Entities use coordinator methods/properties, never the API directly.

    Token refresh is now handled automatically by the aiokwikset library
    via the token_update_callback passed during API initialization.
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
        access_code_store: Store | None = None,
        access_code_data: dict[str, dict[str, Any]] | None = None,
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
        self._last_history_events: list[dict[str, Any]] = []
        self._history_failure_count: int = 0

        # Access code tracking
        self._access_code_store: Store | None = access_code_store
        self._access_code_store_data: dict[str, dict[str, Any]] = access_code_data or {}
        self._device_reported_slots: dict[int, AccessCodeSlotData] = {}

    # -------------------------------------------------------------------------
    # API Call Wrapper
    # -------------------------------------------------------------------------

    async def _api_call_with_retry(
        self,
        api_call: Callable[..., Awaitable[_T]],
        *args: Any,
        **kwargs: Any,
    ) -> _T:
        """Execute API call with retry logic.

        Token refresh is handled automatically by the aiokwikset library.
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                return await api_call(*args, **kwargs)
            except (TokenExpiredError, Unauthenticated) as err:
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
                    translation_key="auth_failed",
                ) from err
            except (RequestError, KwiksetConnectionError) as err:
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
        assert self.api_client.device is not None  # Set after authentication
        result = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        self._device_info = result if result is not None else {}
        LOGGER.debug("Initial device data loaded for %s", self.device_id)

    async def _async_update_data(self) -> KwiksetDeviceData:
        """Fetch current device state."""
        assert self.api_client.device is not None  # Set after authentication
        result = await self._api_call_with_retry(
            self.api_client.device.get_device_info,
            self.device_id,
        )
        info = result if result is not None else {}
        self._device_info = info

        # Fetch device history with retry logic.
        # History is supplemental diagnostic data; failures must not stall the
        # coordinator update.  The Kwikset history_v4 endpoint can be slow or
        # return 504, so we retry a couple of times with a short delay and fall
        # back to previously cached events on persistent failure.
        history_events = self._last_history_events
        history_fetched = False

        for attempt in range(HISTORY_MAX_RETRY_ATTEMPTS):
            try:
                history_response = await asyncio.wait_for(
                    self.api_client.device.get_device_history(
                        self.device_id,
                        top=10,
                    ),
                    timeout=HISTORY_FETCH_TIMEOUT_SECONDS,
                )
                if history_response and isinstance(history_response.get("data"), list):
                    history_events = history_response["data"]
                    self._last_history_events = history_events
                    history_fetched = True
                    break
                # Response present but unexpected shape — log and retry
                LOGGER.debug(
                    "History response for %s had unexpected format "
                    "(attempt %d/%d): keys=%s",
                    self.device_id,
                    attempt + 1,
                    HISTORY_MAX_RETRY_ATTEMPTS,
                    list(history_response.keys()) if history_response else None,
                )
            except TimeoutError:
                LOGGER.debug(
                    "History fetch timed out for %s (attempt %d/%d)",
                    self.device_id,
                    attempt + 1,
                    HISTORY_MAX_RETRY_ATTEMPTS,
                )
            except (RequestError, KwiksetConnectionError) as err:
                LOGGER.debug(
                    "History fetch failed for %s (attempt %d/%d): %s",
                    self.device_id,
                    attempt + 1,
                    HISTORY_MAX_RETRY_ATTEMPTS,
                    err,
                )
            except Exception:
                LOGGER.debug(
                    "Unexpected error fetching history for %s (attempt %d/%d)",
                    self.device_id,
                    attempt + 1,
                    HISTORY_MAX_RETRY_ATTEMPTS,
                    exc_info=True,
                )

            # Short delay before retry (skip delay on last attempt)
            if attempt < HISTORY_MAX_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

        # Graduated logging: warn once on first failure, info on recovery
        if history_fetched:
            if self._history_failure_count > 0:
                LOGGER.info(
                    "History fetch recovered for %s after %d poll(s) without data",
                    self.device_id,
                    self._history_failure_count,
                )
            self._history_failure_count = 0
        else:
            self._history_failure_count += 1
            if self._history_failure_count == 1:
                LOGGER.warning(
                    "History fetch failed for %s — event sensors will show "
                    "unavailable until history data can be retrieved",
                    self.device_id,
                )
            elif self._history_failure_count % 10 == 0:
                LOGGER.warning(
                    "History fetch has failed %d consecutive times for %s",
                    self._history_failure_count,
                    self.device_id,
                )

        # Parse access code slot data from device info
        self._device_reported_slots = self._discover_device_slots(info)
        self._log_access_code_fields(info)

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
            history_events=history_events,
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
    # Real-Time Event Handling
    # -------------------------------------------------------------------------

    @callback
    def handle_realtime_event(self, event_data: dict[str, Any]) -> None:
        """Handle a real-time websocket event and update coordinator data.

        Merges the event data into the current coordinator data and
        triggers entity updates via async_set_updated_data().

        Only updates fields that are present in the event data, preserving
        existing values for fields not included in the event.

        Args:
            event_data: Raw event data from the websocket callback.

        """
        if not self.data:
            LOGGER.debug(
                "Ignoring real-time event for %s \u2014 no initial data yet",
                self.device_id,
            )
            return

        # Start with current data
        updated = dict(self.data)
        original_door_status = self.data.get("door_status")

        # Map event fields to coordinator data fields.
        # Only update fields that are present AND non-None in the event,
        # since the websocket sends None for unchanged fields.
        door_status = event_data.get(_KEY_DOOR_STATUS)
        if door_status is not None:
            updated["door_status"] = door_status

        battery = event_data.get(_KEY_BATTERY)
        if battery is not None:
            updated["battery_percentage"] = battery

        led = event_data.get(_KEY_LED)
        if led is not None:
            updated["led_status"] = self._parse_bool(led)

        audio = event_data.get(_KEY_AUDIO)
        if audio is not None:
            updated["audio_status"] = self._parse_bool(audio)

        secure_screen = event_data.get(_KEY_SECURE_SCREEN)
        if secure_screen is not None:
            updated["secure_screen_status"] = self._parse_bool(secure_screen)

        # Also check for the websocket-specific device status key
        device_status = event_data.get(WEBSOCKET_FIELD_DEVICE_STATUS)
        if device_status is not None:
            updated["door_status"] = device_status

        # Detect whether door status changed so we can request a history
        # refresh from the REST API.  The websocket does not carry event
        # history, so the only reliable source for the Event entity and
        # the Last Lock Event sensor is the history_v4 REST endpoint.
        new_door_status = updated.get("door_status")
        door_status_changed = (
            new_door_status is not None and new_door_status != original_door_status
        )

        # Process access code operation responses
        mq_response_raw = event_data.get(_KEY_LOCK_MQ_RESPONSE)
        if mq_response_raw:
            self._handle_lock_mq_response(mq_response_raw)

        single_crc_raw = event_data.get(_KEY_SINGLE_ACCESS_CODE_CRC)
        if single_crc_raw:
            self._handle_single_access_code_crc(single_crc_raw)

        # Re-parse access code fields if present in event
        for ac_field in (
            _KEY_ACCESS_CODE_CRC,
            _KEY_ACCESS_CODE_64,
            _KEY_ACCESS_CODE_8,
            _KEY_ACCESS_CODE_BY_INDEX,
        ):
            if event_data.get(ac_field) is not None:
                self._device_reported_slots = self._discover_device_slots(event_data)
                break

        LOGGER.debug(
            "Applying real-time update for %s: door_status=%s",
            self.device_id,
            updated.get("door_status"),
        )

        self.async_set_updated_data(KwiksetDeviceData(**updated))

        # After pushing the immediate state update to entities (lock, switches,
        # battery), schedule a coordinator refresh to fetch real event history
        # from the REST API.  This gives the Event entity and Last Lock Event
        # sensor authoritative data with proper IDs, users, and timestamps.
        if door_status_changed:
            LOGGER.debug(
                "Door status changed for %s (%s → %s) — requesting history refresh",
                self.device_id,
                original_door_status,
                new_door_status,
            )
            self.hass.async_create_task(self.async_request_refresh(), eager_start=False)

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
        """Return lock status (Locked/Unlocked/Jammed/Unknown)."""
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
    # History Properties (for history sensor entity)
    # -------------------------------------------------------------------------

    @property
    def history_events(self) -> list[dict[str, Any]]:
        """Return the list of recent history events."""
        if self.data:
            return self.data.get("history_events", [])
        return []

    @property
    def last_event(self) -> str | None:
        """Return the last event description (e.g., 'Locked', 'Unlocked')."""
        events = self.history_events
        if events:
            return events[0].get("event")
        return None

    @property
    def last_event_user(self) -> str | None:
        """Return the user who triggered the last event."""
        events = self.history_events
        if events:
            return events[0].get("user")
        return None

    @property
    def last_event_type(self) -> str | None:
        """Return the type of the last event."""
        events = self.history_events
        if events:
            return events[0].get("eventtype")
        return None

    @property
    def last_event_timestamp(self) -> int | None:
        """Return the unix timestamp of the last event."""
        events = self.history_events
        if events:
            return events[0].get("timestamp")
        return None

    @property
    def last_event_category(self) -> str | None:
        """Return the category of the last event."""
        events = self.history_events
        if events:
            return events[0].get("eventcategory")
        return None

    @property
    def total_events(self) -> int:
        """Return the total number of fetched history events."""
        return len(self.history_events)

    # -------------------------------------------------------------------------
    # Access Code Properties
    # -------------------------------------------------------------------------

    @property
    def access_codes(self) -> dict[int, AccessCodeEntry]:
        """Return merged access code entries (HA metadata + device-reported slots).

        HA-managed entries are authoritative for their slots. Device-reported
        slots that don't have HA metadata are returned with source="device".
        """
        merged: dict[int, AccessCodeEntry] = {}

        # Start with device-reported slots (source="device")
        for slot_idx, slot_data in self._device_reported_slots.items():
            if slot_data["occupied"]:
                merged[slot_idx] = AccessCodeEntry(
                    slot=slot_idx,
                    name="",
                    schedule_type="unknown",
                    enabled=True,
                    source="device",
                    created_at=None,
                    last_updated=None,
                )

        # Overlay HA-managed metadata (authoritative)
        device_store = self._access_code_store_data.get(self.device_id, {})
        for slot_str, entry_data in device_store.items():
            try:
                slot_idx = int(slot_str)
                merged[slot_idx] = AccessCodeEntry(
                    slot=entry_data.get("slot", slot_idx),
                    name=entry_data.get("name", ""),
                    schedule_type=entry_data.get("schedule_type", "unknown"),
                    enabled=entry_data.get("enabled", True),
                    source="ha",
                    created_at=entry_data.get("created_at"),
                    last_updated=entry_data.get("last_updated"),
                )
            except (ValueError, TypeError):
                continue

        return merged

    @property
    def occupied_slots(self) -> list[int]:
        """Return sorted list of occupied slot indices."""
        return sorted(self.access_codes.keys())

    @property
    def total_access_codes(self) -> int:
        """Return total number of known occupied access code slots."""
        return len(self.access_codes)

    # -------------------------------------------------------------------------
    # Access Code Slot Parsing
    # -------------------------------------------------------------------------

    def _parse_access_code_crc(self, raw: Any) -> dict[int, AccessCodeSlotData]:
        """Parse accesscodecrc field for slot occupancy.

        Expected format: Comma-delimited string of CRC tokens, each parseable
        by aiokwikset.parse_single_access_code_crc().
        """
        if not raw or not isinstance(raw, str):
            return {}

        slots: dict[int, AccessCodeSlotData] = {}
        tokens = raw.split(",")

        for raw_token in tokens:
            stripped = raw_token.strip()
            if not stripped:
                continue
            try:
                parsed = parse_single_access_code_crc(stripped)
                if parsed.slot_index is not None:
                    slots[parsed.slot_index] = AccessCodeSlotData(
                        slot=parsed.slot_index,
                        occupied=True,
                        crc_token=parsed.crc_token,
                        raw_data=stripped,
                    )
            except Exception:
                LOGGER.debug(
                    "Could not parse accesscodecrc token for %s: %r",
                    self.device_id,
                    stripped,
                )

        return slots

    def _parse_access_code_bitmap(
        self, raw: Any, max_slots: int
    ) -> dict[int, AccessCodeSlotData]:
        """Parse hex-encoded bitmap for slot occupancy.

        Each bit position represents a slot. Bit=1 means occupied.
        """
        if raw is None:
            return {}

        try:
            if isinstance(raw, str):
                bitmap = int(raw, 16)
            elif isinstance(raw, int):
                bitmap = raw
            else:
                LOGGER.debug(
                    "Unexpected bitmap type for %s: %s (%r)",
                    self.device_id,
                    type(raw).__name__,
                    raw,
                )
                return {}
        except (ValueError, TypeError):
            LOGGER.debug(
                "Could not parse access code bitmap for %s: %r",
                self.device_id,
                raw,
            )
            return {}

        slots: dict[int, AccessCodeSlotData] = {}
        for i in range(max_slots):
            if bitmap & (1 << i):
                slots[i] = AccessCodeSlotData(
                    slot=i,
                    occupied=True,
                    crc_token=None,
                    raw_data=str(raw),
                )

        return slots

    def _parse_access_code_by_index(self, raw: Any) -> dict[int, AccessCodeSlotData]:
        """Parse accesscodebyindex field for per-slot data.

        Format is unknown — try JSON object, JSON array, and CSV.
        Log the raw value at debug level to help reverse-engineer the format.
        """
        if not raw:
            return {}

        LOGGER.debug(
            "accesscodebyindex raw value for %s (type=%s): %r",
            self.device_id,
            type(raw).__name__,
            raw,
        )

        # Attempt 1: JSON object {"0": {...}, "1": {...}}
        if isinstance(raw, dict):
            return self._parse_abi_dict(raw)

        if isinstance(raw, str):
            raw = raw.strip()
            # Attempt 2: JSON string
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return self._parse_abi_dict(parsed)
                if isinstance(parsed, list):
                    return self._parse_abi_list(parsed)
            except (json.JSONDecodeError, ValueError):
                pass

            # Attempt 3: CSV — log and skip for now
            LOGGER.debug(
                "Could not parse accesscodebyindex as JSON for %s: %r",
                self.device_id,
                raw[:200],
            )

        return {}

    def _parse_abi_dict(self, data: dict) -> dict[int, AccessCodeSlotData]:
        """Parse accesscodebyindex when it's a dict keyed by slot index."""
        slots: dict[int, AccessCodeSlotData] = {}
        for key, value in data.items():
            try:
                slot_idx = int(key)
                occupied = bool(value)
                slots[slot_idx] = AccessCodeSlotData(
                    slot=slot_idx,
                    occupied=occupied,
                    crc_token=None,
                    raw_data=str(value)[:100],
                )
            except (ValueError, TypeError):
                continue
        return slots

    def _parse_abi_list(self, data: list) -> dict[int, AccessCodeSlotData]:
        """Parse accesscodebyindex when it's a list indexed by slot."""
        slots: dict[int, AccessCodeSlotData] = {}
        for idx, value in enumerate(data):
            if value:
                slots[idx] = AccessCodeSlotData(
                    slot=idx,
                    occupied=True,
                    crc_token=None,
                    raw_data=str(value)[:100],
                )
        return slots

    def _discover_device_slots(
        self, info: dict[str, Any]
    ) -> dict[int, AccessCodeSlotData]:
        """Discover occupied slots from all device info fields.

        Merges data from multiple sources. CRC data takes precedence for
        crc_token values; bitmap data fills in gaps.
        """
        slots: dict[int, AccessCodeSlotData] = {}

        # Merge: bitmap → crc → index (increasing specificity)
        bitmap_64 = self._parse_access_code_bitmap(
            info.get(_KEY_ACCESS_CODE_64), max_slots=64
        )
        bitmap_8 = self._parse_access_code_bitmap(
            info.get(_KEY_ACCESS_CODE_8), max_slots=8
        )
        crc_slots = self._parse_access_code_crc(info.get(_KEY_ACCESS_CODE_CRC))
        index_slots = self._parse_access_code_by_index(
            info.get(_KEY_ACCESS_CODE_BY_INDEX)
        )

        slots.update(bitmap_64)
        slots.update(bitmap_8)
        slots.update(crc_slots)
        slots.update(index_slots)

        if slots:
            LOGGER.debug(
                "Discovered %d occupied slot(s) for %s from device data: %s",
                len(slots),
                self.device_id,
                sorted(slots.keys()),
            )

        return slots

    def _log_access_code_fields(self, info: dict[str, Any]) -> None:
        """Log raw access code fields for debugging (on value change only)."""
        fields = [
            _KEY_ACCESS_CODE_CRC,
            _KEY_ACCESS_CODE_64,
            _KEY_ACCESS_CODE_8,
            _KEY_ACCESS_CODE_BY_INDEX,
        ]
        for ac_field in fields:
            value = info.get(ac_field)
            if value is not None:
                cache_key = f"_last_{ac_field}"
                last_value = getattr(self, cache_key, None)
                if value != last_value:
                    LOGGER.debug(
                        "Access code field '%s' for %s (type=%s): %r",
                        ac_field,
                        self.device_id,
                        type(value).__name__,
                        str(value)[:500],
                    )
                    setattr(self, cache_key, value)

    # -------------------------------------------------------------------------
    # Access Code Websocket Handlers
    # -------------------------------------------------------------------------

    def _handle_lock_mq_response(self, raw: Any) -> None:
        """Process lockmqresponse field from websocket event."""
        if not raw:
            return

        try:
            parsed = parse_lock_mq_response(raw)
        except Exception:
            LOGGER.debug(
                "Could not parse lockmqresponse for %s: %r",
                self.device_id,
                raw,
            )
            return

        LOGGER.debug(
            "Lock MQ response for %s: command=%s slot=%s enabled=%s",
            self.device_id,
            parsed.command,
            parsed.slot_index,
            parsed.enabled,
        )

        if parsed.command == MqttCommandType.SET_ACCESS_CODE:
            if parsed.slot_index is not None:
                self.hass.async_create_task(
                    self.async_resolve_pending_slot(parsed.slot_index),
                    eager_start=False,
                )
                self._device_reported_slots[parsed.slot_index] = AccessCodeSlotData(
                    slot=parsed.slot_index,
                    occupied=True,
                    crc_token=None,
                    raw_data=str(raw),
                )
        elif parsed.command == MqttCommandType.DELETE_ACCESS_CODE:
            if parsed.slot_index is not None:
                self._device_reported_slots.pop(parsed.slot_index, None)
        elif (
            parsed.command == MqttCommandType.EDIT_ACCESS_CODE
            and parsed.slot_index is not None
        ):
            self._device_reported_slots[parsed.slot_index] = AccessCodeSlotData(
                slot=parsed.slot_index,
                occupied=True,
                crc_token=None,
                raw_data=str(raw),
            )

    def _handle_single_access_code_crc(self, raw: Any) -> None:
        """Process singleAccessCodeCrc field — slot assignment confirmation."""
        if not raw:
            return

        try:
            parsed = parse_single_access_code_crc(raw)
        except Exception:
            LOGGER.debug(
                "Could not parse singleAccessCodeCrc for %s: %r",
                self.device_id,
                raw,
            )
            return

        LOGGER.debug(
            "Single access code CRC for %s: slot=%s crc_token=%s",
            self.device_id,
            parsed.slot_index,
            parsed.crc_token,
        )

        if parsed.slot_index is not None:
            self._device_reported_slots[parsed.slot_index] = AccessCodeSlotData(
                slot=parsed.slot_index,
                occupied=True,
                crc_token=parsed.crc_token,
                raw_data=str(raw),
            )
            self.hass.async_create_task(
                self.async_resolve_pending_slot(parsed.slot_index),
                eager_start=False,
            )

    # -------------------------------------------------------------------------
    # Access Code Store Mutations
    # -------------------------------------------------------------------------

    def get_tracked_code(self, slot: int) -> AccessCodeEntry | None:
        """Retrieve stored metadata for a tracked access code slot.

        Returns None if the slot is not tracked or has no HA-managed data.
        """
        device_store = self._access_code_store_data.get(self.device_id, {})
        entry = device_store.get(str(slot))
        if entry and entry.get("source") == "ha":
            return AccessCodeEntry(
                slot=entry["slot"],
                name=entry.get("name", ""),
                code=entry.get("code", ""),
                schedule_type=entry.get("schedule_type", "all_day"),
                enabled=entry.get("enabled", True),
                source=entry["source"],
                created_at=entry.get("created_at"),
                last_updated=entry.get("last_updated"),
            )
        return None

    async def async_track_access_code(
        self,
        slot: int,
        name: str,
        code: str,
        schedule_type: str,
        enabled: bool = True,
    ) -> None:
        """Track an HA-managed access code in persistent store."""
        now = datetime.now(tz=UTC).isoformat()
        device_store = self._access_code_store_data.setdefault(self.device_id, {})

        existing = device_store.get(str(slot))
        created_at = existing.get("created_at", now) if existing else now

        device_store[str(slot)] = {
            "slot": slot,
            "name": name,
            "code": code,
            "schedule_type": schedule_type,
            "enabled": enabled,
            "source": "ha",
            "created_at": created_at,
            "last_updated": now,
        }

        await self._async_save_store()

    async def async_update_access_code_enabled(self, slot: int, enabled: bool) -> None:
        """Update enabled status for an existing tracked code."""
        device_store = self._access_code_store_data.get(self.device_id, {})
        entry = device_store.get(str(slot))
        if entry:
            entry["enabled"] = enabled
            entry["last_updated"] = datetime.now(tz=UTC).isoformat()
            await self._async_save_store()
        else:
            LOGGER.debug(
                "Cannot update enabled status for untracked slot %d on %s",
                slot,
                self.device_id,
            )

    async def async_remove_access_code(self, slot: int) -> None:
        """Remove a tracked access code from persistent store."""
        device_store = self._access_code_store_data.get(self.device_id, {})
        if device_store.pop(str(slot), None) is not None:
            await self._async_save_store()

    async def async_remove_all_access_codes(self) -> None:
        """Remove all tracked access codes for this device."""
        if self._access_code_store_data.pop(self.device_id, None) is not None:
            await self._async_save_store()

    async def async_resolve_pending_slot(self, actual_slot: int) -> None:
        """Migrate a pending slot-0 entry to its actual assigned slot."""
        device_store = self._access_code_store_data.get(self.device_id, {})
        pending = device_store.pop("0", None)
        if pending and pending.get("source") == "ha":
            pending["slot"] = actual_slot
            pending["last_updated"] = datetime.now(tz=UTC).isoformat()
            device_store[str(actual_slot)] = pending
            await self._async_save_store()
            LOGGER.debug(
                "Resolved pending access code to slot %d on %s",
                actual_slot,
                self.device_id,
            )

    async def _async_save_store(self) -> None:
        """Persist access code metadata to disk."""
        if self._access_code_store is not None:
            await self._access_code_store.async_save(self._access_code_store_data)

    # -------------------------------------------------------------------------
    # Device Actions (called by entity platforms)
    # -------------------------------------------------------------------------

    async def _get_user_info(self) -> dict[str, Any]:
        """Get user info required for lock/unlock commands."""
        assert self.api_client.user is not None  # Set after authentication
        result = await self._api_call_with_retry(self.api_client.user.get_info)
        return result if result is not None else {}

    async def lock(self) -> None:
        """Lock the device."""
        assert self.api_client.device is not None  # Set after authentication
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
        assert self.api_client.device is not None  # Set after authentication
        user_info = await self._get_user_info()
        await self._api_call_with_retry(
            self.api_client.device.unlock_device,
            self._device_info,
            user_info,
        )
        LOGGER.debug("Unlock command sent for %s", self.device_id)
        await self.async_request_refresh()

    async def set_led(self, enabled: bool) -> None:
        """Set LED status using convenience method."""
        assert self.api_client.device is not None  # Set after authentication
        await self._api_call_with_retry(
            self.api_client.device.set_led_enabled,
            self._device_info,
            enabled,
        )
        LOGGER.debug("LED set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()

    async def set_audio(self, enabled: bool) -> None:
        """Set audio status using convenience method."""
        assert self.api_client.device is not None  # Set after authentication
        await self._api_call_with_retry(
            self.api_client.device.set_audio_enabled,
            self._device_info,
            enabled,
        )
        LOGGER.debug("Audio set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()

    async def set_secure_screen(self, enabled: bool) -> None:
        """Set secure screen status using convenience method."""
        assert self.api_client.device is not None  # Set after authentication
        await self._api_call_with_retry(
            self.api_client.device.set_secure_screen_enabled,
            self._device_info,
            enabled,
        )
        LOGGER.debug("Secure screen set to %s for %s", enabled, self.device_id)
        await self.async_request_refresh()

    # -------------------------------------------------------------------------
    # Access Code Actions
    # -------------------------------------------------------------------------

    async def create_access_code(
        self,
        code: str,
        name: str,
        schedule: AccessCodeSchedule,
        slot: int = 0,
        enabled: bool = True,
    ) -> AccessCodeResult:
        """Create an access code on the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.create_access_code,
            self.device_id,
            code,
            name,
            schedule,
            slot=slot,
            enabled=enabled,
        )
        LOGGER.debug(
            "Access code created for %s: token=%s", self.device_id, result.token
        )
        return result

    async def edit_access_code(
        self,
        code: str,
        name: str,
        schedule: AccessCodeSchedule,
        slot: int,
        enabled: bool = True,
    ) -> AccessCodeResult:
        """Edit an existing access code on the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.edit_access_code,
            self.device_id,
            code,
            name,
            schedule,
            slot,
            enabled=enabled,
        )
        LOGGER.debug("Access code edited for %s slot %d", self.device_id, slot)
        return result

    async def disable_access_code(
        self,
        code: str,
        name: str,
        schedule: AccessCodeSchedule,
        slot: int,
    ) -> AccessCodeResult:
        """Disable an access code on the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.disable_access_code,
            self.device_id,
            code,
            name,
            schedule,
            slot,
        )
        LOGGER.debug("Access code disabled for %s slot %d", self.device_id, slot)
        return result

    async def enable_access_code(
        self,
        code: str,
        name: str,
        schedule: AccessCodeSchedule,
        slot: int,
    ) -> AccessCodeResult:
        """Enable an access code on the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.enable_access_code,
            self.device_id,
            code,
            name,
            schedule,
            slot,
        )
        LOGGER.debug("Access code enabled for %s slot %d", self.device_id, slot)
        return result

    async def delete_access_code(self, slot: int) -> dict[str, Any]:
        """Delete a single access code from the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.delete_access_code,
            self.device_id,
            slot,
        )
        LOGGER.debug("Access code deleted from %s slot %d", self.device_id, slot)
        return result

    async def delete_all_access_codes(self) -> dict[str, Any]:
        """Delete all access codes from the device."""
        assert self.api_client.device is not None
        result = await self._api_call_with_retry(
            self.api_client.device.delete_all_access_codes,
            self.device_id,
        )
        LOGGER.debug("All access codes deleted from %s", self.device_id)
        return result

    def set_update_interval(self, interval: timedelta) -> None:
        """Set the update interval for polling.

        This method exists to provide a type-safe way to update the interval,
        as the base class property may be typed as read-only in some stubs.
        """
        # Use object.__setattr__ to bypass any read-only typing issues
        object.__setattr__(self, "update_interval", interval)
