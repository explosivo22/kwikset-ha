"""Constants for Kwikset Smart Locks integration.

This module defines all constants used throughout the Kwikset integration.
Following Home Assistant conventions:
- Use Final type hints for immutable constants
- Group related constants with comments
- Prefer HA's built-in constants (CONF_EMAIL, CONF_PASSWORD) over custom ones
"""

from __future__ import annotations

import logging
from typing import Final

# Integration logger - uses package name for proper log filtering
LOGGER = logging.getLogger(__package__)

# Domain identifier - must match manifest.json domain
DOMAIN: Final = "kwikset"

# Configuration keys stored in config_entry.data
# Note: We use HA's CONF_EMAIL, CONF_PASSWORD from homeassistant.const
CONF_HOME_ID: Final = "conf_home_id"
CONF_ID_TOKEN: Final = "conf_id_token"
CONF_ACCESS_TOKEN: Final = "conf_access_token"
CONF_REFRESH_TOKEN: Final = "conf_refresh_token"

# Password storage (optional - for automatic re-authentication)
CONF_SAVE_PASSWORD: Final = "save_password"
CONF_STORED_PASSWORD: Final = "stored_password"
DEFAULT_SAVE_PASSWORD: Final = False

# Configuration keys stored in config_entry.options
CONF_REFRESH_INTERVAL: Final = "refresh_interval"

# Default polling interval in seconds (configurable 30-900s via options flow)
DEFAULT_REFRESH_INTERVAL: Final = 30
MIN_REFRESH_INTERVAL: Final = 30
MAX_REFRESH_INTERVAL: Final = 900

# Retry settings for transient API failures (network issues, rate limits)
MAX_RETRY_ATTEMPTS: Final = 3
RETRY_DELAY_SECONDS: Final = 2

# History API fetch timeout per attempt (non-critical supplemental data).
# Kwikset's history_v4 endpoint can be slow; this must be long enough for the
# aiokwikset library's own request + retry cycle to complete.  A value equal to
# aiokwikset's DEFAULT_TIMEOUT (30 s) gives the endpoint a fair chance while
# still preventing indefinite blocking of the coordinator update.
HISTORY_FETCH_TIMEOUT_SECONDS: Final = 30

# Number of retry attempts for fetching device history.
# History is supplemental — retries are lightweight and avoid a single
# transient failure leaving sensors at Unknown for an entire poll cycle.
HISTORY_MAX_RETRY_ATTEMPTS: Final = 2

# Optimistic timeout for lock/unlock operations
# After sending a command, we optimistically show the transitional state
# (locking/unlocking) until either the API confirms or this timeout expires.
# 30 seconds is used by the Matter lock integration as a safe default.
OPTIMISTIC_TIMEOUT_SECONDS: Final = 30

# Limit concurrent API calls per platform to prevent rate limiting
# Each platform file uses this value to serialize entity operations
PARALLEL_UPDATES: Final = 1

# Access code service names
SERVICE_CREATE_ACCESS_CODE: Final = "create_access_code"
SERVICE_EDIT_ACCESS_CODE: Final = "edit_access_code"
SERVICE_DISABLE_ACCESS_CODE: Final = "disable_access_code"
SERVICE_ENABLE_ACCESS_CODE: Final = "enable_access_code"
SERVICE_DELETE_ACCESS_CODE: Final = "delete_access_code"
SERVICE_DELETE_ALL_ACCESS_CODES: Final = "delete_all_access_codes"
SERVICE_LIST_ACCESS_CODES: Final = "list_access_codes"

# Access code persistent store
STORAGE_KEY: Final = f"{DOMAIN}_access_codes"
STORAGE_VERSION: Final = 1

# Access code source identifiers
ACCESS_CODE_SOURCE_HA: Final = "ha"
ACCESS_CODE_SOURCE_DEVICE: Final = "device"

# Access code schedule type constants
SCHEDULE_TYPE_ALL_DAY: Final = "all_day"
SCHEDULE_TYPE_DATE_RANGE: Final = "date_range"
SCHEDULE_TYPE_WEEKLY: Final = "weekly"
SCHEDULE_TYPE_ONE_TIME_UNLIMITED: Final = "one_time_unlimited"
SCHEDULE_TYPE_ONE_TIME_24_HOUR: Final = "one_time_24_hour"

# Home user management service names
SERVICE_INVITE_USER: Final = "invite_user"
SERVICE_UPDATE_USER: Final = "update_user"
SERVICE_DELETE_USER: Final = "delete_user"
SERVICE_LIST_USERS: Final = "list_users"

# Home user access levels
ACCESS_LEVEL_MEMBER: Final = "Member"
ACCESS_LEVEL_ADMIN: Final = "Admin"

# WebSocket event constants (aiokwikset subscriptions API)
WEBSOCKET_EVENT_MANAGE_DEVICE: Final = "onManageDevice"
WEBSOCKET_FIELD_DEVICE_ID: Final = "deviceid"
WEBSOCKET_FIELD_DEVICE_STATUS: Final = "devicestatus"

# When the websocket is connected, polling becomes a safety-net heartbeat
# at this longer interval instead of the user-configured interval.
WEBSOCKET_FALLBACK_POLL_INTERVAL: Final = 900
