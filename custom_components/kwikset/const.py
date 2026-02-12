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

# Configuration keys stored in config_entry.options
CONF_REFRESH_INTERVAL: Final = "refresh_interval"

# Default polling interval in seconds (configurable 30-900s via options flow)
DEFAULT_REFRESH_INTERVAL: Final = 30
MIN_REFRESH_INTERVAL: Final = 30
MAX_REFRESH_INTERVAL: Final = 900

# Retry settings for transient API failures (network issues, rate limits)
MAX_RETRY_ATTEMPTS: Final = 3
RETRY_DELAY_SECONDS: Final = 2

# Optimistic timeout for lock/unlock operations
# After sending a command, we optimistically show the transitional state
# (locking/unlocking) until either the API confirms or this timeout expires.
# 30 seconds is used by the Matter lock integration as a safe default.
OPTIMISTIC_TIMEOUT_SECONDS: Final = 30

# Limit concurrent API calls per platform to prevent rate limiting
# Each platform file uses this value to serialize entity operations
PARALLEL_UPDATES: Final = 1
