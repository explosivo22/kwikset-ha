# Dynamic Device Discovery Implementation

## Overview

This implementation adds support for automatic discovery of new devices and removal of stale devices in the Kwikset Home Assistant custom component, following Home Assistant best practices.

## Problem Solved

Previously, if a user configured the integration for a specific home and later added new Kwikset devices to that home, those new devices would not appear in Home Assistant. The user would need to remove and reconfigure the entire integration to see new devices, which was not possible because the home was already configured (unique constraint).

## Solution

The implementation follows the official Home Assistant patterns for dynamic device management:

### 1. Device Tracking (`__init__.py`)

- **Changed devices storage from list to dictionary**: Devices are now stored as `dict[device_id, coordinator]` for efficient lookup
- **Added known_devices tracking**: Maintains a set of device IDs that have been discovered
- **Periodic device check**: Every 5 minutes, the integration queries the Kwikset API to check for new or removed devices
- **Automatic device discovery**: When new devices are detected, coordinators are created and the integration reloads to set up entities
- **Stale device removal**: When devices are no longer returned by the API, they are removed from the device registry

### 2. Platform Updates (`lock.py`, `sensor.py`, `switch.py`)

Each platform now implements a dynamic entity callback pattern:

```python
@callback
def _add_new_devices() -> None:
    """Add new entities for newly discovered devices."""
    # Track which devices have been added
    # Only create entities for new devices
    # Add entities dynamically
```

This ensures that when the integration reloads due to new device discovery, entities are created for all devices.

### 3. User-Triggered Discovery

#### Options Flow
- Added a "Reload integration to discover new devices" checkbox in the integration options
- When enabled, triggers an immediate reload to discover new devices

#### Reconfigure Flow
- Added a reconfigure step (`async_step_reconfigure`) following Home Assistant 2024.3+ best practices
- Allows users to manually trigger device discovery from the UI
- Accessible via the integration's three-dot menu → "Reconfigure"

## Home Assistant Best Practices Implemented

1. **Dynamic Device Discovery** - [Rule: dynamic-devices](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dynamic-devices/)
   - Entities are added dynamically when new devices are discovered
   - Uses coordinator pattern with callback listeners

2. **Stale Device Removal** - [Rule: stale-devices](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/stale-devices/)
   - Devices are removed from device registry when no longer available
   - Uses `device_registry.async_update_device()` with `remove_config_entry_id`

3. **Config Entry Reconfigure** - [Blog: Config Entry Reconfigure Step](https://developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step/)
   - Implements `async_step_reconfigure()` for user-initiated reconfiguration
   - Provides UI access to trigger device discovery

4. **Proper Entity Management**
   - Uses `@callback` decorator for efficient entity callbacks
   - Properly tracks known entities to avoid duplicates
   - Implements cleanup with `config_entry.async_on_unload()`

## Usage

### Automatic Discovery
New devices are automatically discovered every 5 minutes. When detected:
1. New coordinators are created
2. Integration reloads automatically
3. Entities appear in Home Assistant
4. Notification appears in UI (if enabled)

### Manual Discovery

#### Via Options:
1. Go to Settings → Devices & Services
2. Find the Kwikset integration
3. Click "Configure"
4. Check "Reload integration to discover new devices"
5. Click "Submit"

#### Via Reconfigure:
1. Go to Settings → Devices & Services
2. Find the Kwikset integration
3. Click the three-dot menu → "Reconfigure"
4. Click "Submit"
5. Integration reloads and discovers new devices

## Technical Details

### Device Lifecycle

```
Initial Setup:
1. User configures integration with home ID
2. API fetches all devices for that home
3. Coordinators created for each device
4. Entities created for each coordinator

During Runtime:
1. Every 5 minutes: _async_update_devices() runs
2. Queries API for current device list
3. Compares with known_devices set
4. If new devices found:
   - Creates coordinators
   - Triggers integration reload
   - Entities created via platform callbacks
5. If devices removed:
   - Removes from device registry
   - Cleans up coordinators

User-Triggered:
1. User clicks reconfigure or checks option
2. Integration reloads immediately
3. Same process as periodic check runs
```

### Data Structure Changes

**Before:**
```python
hass.data[DOMAIN][entry.entry_id]["devices"] = [
    coordinator1, coordinator2, ...
]
```

**After:**
```python
hass.data[DOMAIN][entry.entry_id]["devices"] = {
    "device_id_1": coordinator1,
    "device_id_2": coordinator2,
    ...
}
hass.data[DOMAIN][entry.entry_id]["known_devices"] = {
    "device_id_1", "device_id_2", ...
}
```

## Migration Notes

This implementation is backward compatible with the existing setup. When users update:
1. Existing devices continue to work
2. Device tracking begins automatically
3. New devices will be discovered on next check (within 5 minutes)
4. No user action required

## Testing Recommendations

1. **Add new device test:**
   - Set up integration with one device
   - Add a second device to Kwikset account
   - Wait 5 minutes or trigger manual discovery
   - Verify new device appears

2. **Remove device test:**
   - Set up integration with two devices
   - Remove one device from Kwikset account
   - Wait 5 minutes
   - Verify device is removed from Home Assistant

3. **Options flow test:**
   - Open integration options
   - Check "Reload integration" checkbox
   - Verify integration reloads
   - Verify devices are discovered

4. **Reconfigure test:**
   - Use reconfigure menu option
   - Verify integration reloads
   - Verify new devices appear

## References

- [Home Assistant Integration Quality Scale Rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Dynamic Devices Pattern](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dynamic-devices/)
- [Stale Device Removal](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/stale-devices/)
- [Config Entry Reconfigure](https://developers.home-assistant.io/blog/2024/03/21/config-entry-reconfigure-step/)
- [Device Registry Documentation](https://developers.home-assistant.io/docs/device_registry_index/)
