# Kwikset Smart Locks for Home Assistant

[![License](https://img.shields.io/github/license/explosivo22/kwikset-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![Validate](https://github.com/explosivo22/kwikset-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/explosivo22/kwikset-ha/actions/workflows/validate.yml)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.kwikset.total&style=for-the-badge&logo=home-assistant&label=integration%20usage&color=41BDF5)](https://analytics.home-assistant.io/custom_integrations.json)
[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Gold-gold?style=for-the-badge)](https://developers.home-assistant.io/docs/core/integration-quality-scale)

<a href="https://www.buymeacoffee.com/Explosivo22" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

A custom Home Assistant integration for [Kwikset Smart Locks](https://www.kwikset.com/products/electronic/electronic-smart-locks) using the unofficial Kwikset cloud API. Control and monitor your Kwikset smart locks directly from Home Assistant.

---

## 📋 Table of Contents

- [Features](#-features)
- [Supported Devices](#-supported-devices)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Entities](#-entities)
- [Use Cases & Automations](#-use-cases--automations)
- [Troubleshooting](#-troubleshooting)
- [Quality Scale Compliance](#-quality-scale-compliance)
- [Contributing](#-contributing)
- [Support](#-support)

---

## ✨ Features

### Lock Control
- **Lock/Unlock**: Control your Kwikset smart locks remotely
- **Real-time Status**: View lock state (locked/unlocked) with automatic polling
- **Battery Monitoring**: Track battery percentage with low battery alerts

### Device Settings
- **LED Indicator**: Toggle the LED status light on/off
- **Audio Feedback**: Enable/disable keypad sounds
- **Secure Screen**: Control the secure screen display mode

### Smart Features
- **Multi-Home Support**: Configure multiple Kwikset homes in a single HA instance
- **Dynamic Device Discovery**: New locks are automatically detected every 5 minutes
- **Stale Device Removal**: Devices removed from your account are automatically cleaned up
- **MFA Support**: Full multi-factor authentication support (SMS and authenticator apps)
- **Proactive Token Refresh**: Authentication tokens are refreshed before expiry

### Connection Modes

| Mode | Description | Polling Interval |
|------|-------------|------------------|
| Cloud Polling | Connects via Kwikset cloud API | 15-60 seconds (configurable) |

> **Note**: This integration uses cloud polling only. Local/Bluetooth control is not supported as Kwikset does not provide a local API.

---

## 🔐 Supported Devices

This integration supports Kwikset smart locks that are compatible with the Kwikset app:

| Product Line | Models | Features |
|--------------|--------|----------|
| **Halo Series** | Halo, Halo Touch | WiFi, Fingerprint (Touch) |
| **Aura Series** | Aura | Bluetooth + WiFi Bridge |
| **Obsidian** | Obsidian | Bluetooth + WiFi Bridge |
| **Premis** | Premis | HomeKit, Bluetooth |
| **SmartCode** | 916, 914, 913 | Z-Wave/Zigbee (via Kwikset app) |

> **Compatibility**: Any lock that can be controlled via the [Kwikset iOS/Android app](https://www.kwikset.com/smart-locks/app) should work with this integration.

### Verified Working Models
- Kwikset Halo Touch (WiFi + Fingerprint)
- Kwikset Halo (WiFi)
- Kwikset Aura (Bluetooth + WiFi Bridge)

---

## 📌 Requirements

### Prerequisites

1. **Kwikset Account**: A valid Kwikset account with your locks registered
2. **Kwikset Home**: You must create a "Home" in the Kwikset app and add your locks to it
3. **Home Assistant**: Version 2024.1.0 or newer recommended
4. **HACS**: For easy installation (optional but recommended)

### Important Notes

> ⚠️ **KWIKSET DOESN'T PROVIDE AN OFFICIALLY SUPPORTED API**
> 
> This integration uses an unofficial API. Kwikset may change their API at any time, which could temporarily break this integration.

> ⚠️ **HOME SETUP REQUIRED**
> 
> This integration only works if you have created a Home in the Kwikset app or have been invited to a Home. Locks must be assigned to a Home.

---

## 📦 Installation

### Option 1: HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=explosivo22&repository=kwikset-ha&category=integration)

1. Click the button above, or:
   - Open HACS in Home Assistant
   - Click "Integrations"
   - Click the three dots menu → "Custom repositories"
   - Add `https://github.com/explosivo22/kwikset-ha` as an Integration
2. Search for "Kwikset Smart Locks" and install
3. Restart Home Assistant
4. Continue to [Configuration](#-configuration)

### Option 2: Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/explosivo22/kwikset-ha/releases)
2. Extract and copy the `kwikset` folder to your `custom_components` directory:
   ```
   config/
   └── custom_components/
       └── kwikset/
           ├── __init__.py
           ├── config_flow.py
           ├── const.py
           └── ...
   ```
3. Restart Home Assistant
4. Continue to [Configuration](#-configuration)

> ⚠️ **Manual Installation Warning**: You won't receive automatic update notifications. Subscribe to repository releases for update alerts.

---

## ⚙️ Configuration

### Initial Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=kwikset)

1. Click the button above, or:
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for "Kwikset Smart Locks"
2. Enter your Kwikset account credentials (email and password)
3. If MFA is enabled, enter the verification code
4. Select the Kwikset Home to configure
5. Done! Your locks will appear as devices

### Installation Parameters

The following parameters are required during the integration setup:

| Parameter | Required | Description |
|-----------|----------|-------------|
| **Email** | Yes | The email address associated with your Kwikset account. This is the same email you use to log into the Kwikset mobile app. |
| **Password** | Yes | Your Kwikset account password. This is stored securely and used to authenticate with the Kwikset cloud API. |
| **Verification Code** | Conditional | A 6-digit code required if you have Multi-Factor Authentication (MFA) enabled on your Kwikset account. The code is sent via SMS or generated by your authenticator app, depending on your MFA configuration. |
| **Home** | Yes | Select which Kwikset home to configure. Each home is set up as a separate integration entry. Only homes that haven't been configured yet will be shown. |

> **Note**: Your credentials are used to authenticate with the Kwikset cloud API. Access and refresh tokens are stored locally and automatically renewed. Your password is only used during initial setup and reauthentication.

### Configuration Options

After setup, you can configure the integration options by going to **Settings** → **Devices & Services**, finding the Kwikset integration, and clicking **Configure**.

| Option | Description | Default | Range |
|--------|-------------|---------|-------|
| **Polling interval** | How often to poll the Kwikset cloud for device status updates. Lower values provide faster status updates but increase API requests. Higher values reduce API load but status updates will be less frequent. | 30 seconds | 15-60 seconds |

> **Tip**: A 30-second polling interval is recommended for most users. Reduce to 15 seconds if you need faster feedback, or increase to 60 seconds if you rarely check lock status remotely.

### Multiple Homes

To add additional Kwikset homes:
1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Kwikset Smart Locks"
4. Enter credentials and select the next home

Each home creates a separate integration entry.

---

## 🗑️ Removal

### Removing the Integration

To remove the Kwikset integration from Home Assistant:

1. Go to **Settings** → **Devices & Services**
2. Find the **Kwikset Smart Locks** integration
3. Click the three dots menu (⋮) on the integration card
4. Select **Delete**
5. Confirm the removal

This will remove all Kwikset devices and entities from Home Assistant. Your Kwikset account and locks are not affected.

### Uninstalling via HACS

To completely uninstall the integration:

1. First, remove the integration (steps above)
2. Open **HACS** → **Integrations**
3. Find "Kwikset Smart Locks"
4. Click the three dots menu (⋮)
5. Select **Remove** → **Remove**
6. Restart Home Assistant

### Manual Uninstallation

If you installed manually:

1. First, remove the integration from Settings (steps above)
2. Delete the `custom_components/kwikset` folder
3. Restart Home Assistant

---

## 🎛️ Entities

Each Kwikset lock creates the following entities:

### Lock Entity
| Entity | Type | Description |
|--------|------|-------------|
| `lock.<device_name>_lock` | Lock | Lock/unlock control and state |

### Sensor Entities
| Entity | Type | Category | Description |
|--------|------|----------|-------------|
| `sensor.<device_name>_battery` | Sensor | Diagnostic | Battery percentage (0-100%) |

### Switch Entities
| Entity | Type | Category | Description |
|--------|------|----------|-------------|
| `switch.<device_name>_led` | Switch | Config | LED indicator on/off |
| `switch.<device_name>_audio` | Switch | Config | Audio feedback on/off |
| `switch.<device_name>_secure_screen` | Switch | Config | Secure screen mode on/off |

### Service Actions

This integration uses standard Home Assistant service actions:

#### Lock Actions
| Action | Description | Example |
|--------|-------------|---------|
| `lock.lock` | Lock the door | `service: lock.lock`<br>`target: entity_id: lock.front_door_lock` |
| `lock.unlock` | Unlock the door | `service: lock.unlock`<br>`target: entity_id: lock.front_door_lock` |

#### Switch Actions
| Action | Description | Example |
|--------|-------------|---------|
| `switch.turn_on` | Enable a setting | `service: switch.turn_on`<br>`target: entity_id: switch.front_door_led` |
| `switch.turn_off` | Disable a setting | `service: switch.turn_off`<br>`target: entity_id: switch.front_door_led` |
| `switch.toggle` | Toggle a setting | `service: switch.toggle`<br>`target: entity_id: switch.front_door_audio` |

> **Note**: This integration does not provide custom service actions. All functionality uses standard Home Assistant lock and switch services.

---

## 🏠 Use Cases & Automations

### Example 1: Auto-Lock at Night

```yaml
automation:
  - alias: "Auto-lock front door at night"
    trigger:
      - platform: time
        at: "22:00:00"
    condition:
      - condition: state
        entity_id: lock.front_door_lock
        state: "unlocked"
    action:
      - service: lock.lock
        target:
          entity_id: lock.front_door_lock
      - service: notify.mobile_app
        data:
          message: "Front door has been auto-locked for the night"
```

### Example 2: Low Battery Alert

```yaml
automation:
  - alias: "Kwikset low battery alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.front_door_battery
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: "🔋 Low Battery Alert"
          message: "Front door lock battery is at {{ states('sensor.front_door_battery') }}%"
```

### Example 3: Welcome Home Unlock

```yaml
automation:
  - alias: "Unlock when arriving home"
    trigger:
      - platform: zone
        entity_id: person.john
        zone: zone.home
        event: enter
    condition:
      - condition: state
        entity_id: lock.front_door_lock
        state: "locked"
      - condition: time
        after: "06:00:00"
        before: "23:00:00"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door_lock
```

### Example 4: Lock Status Dashboard Card

```yaml
type: entities
title: Front Door Lock
entities:
  - entity: lock.front_door_lock
  - entity: sensor.front_door_battery
  - entity: switch.front_door_led
  - entity: switch.front_door_audio
```

### Example 5: Guest Access Notification

```yaml
automation:
  - alias: "Notify when lock state changes"
    trigger:
      - platform: state
        entity_id: lock.front_door_lock
    action:
      - service: notify.mobile_app
        data:
          title: "🔐 Lock Status Changed"
          message: >
            Front door was {{ trigger.to_state.state }} at 
            {{ now().strftime('%I:%M %p') }}
```

---

## 🔧 Troubleshooting

### Common Issues

#### "Cannot connect" error during setup

**Cause**: Network issue or Kwikset API unavailable

**Solutions**:
1. Check your internet connection
2. Verify Kwikset app works on your phone
3. Try again in a few minutes (API may be temporarily down)
4. Check Kwikset server status

#### "Invalid authentication" error

**Cause**: Incorrect credentials or expired session

**Solutions**:
1. Verify email and password are correct
2. Try logging into the Kwikset app to confirm credentials
3. Reset your Kwikset password if needed

#### MFA verification code not working

**Cause**: Code expired or incorrect MFA type

**Solutions**:
1. Ensure you're using the most recent code
2. Check the correct MFA method (SMS vs authenticator app)
3. Codes expire quickly - enter within 30 seconds

#### "No available homes" error

**Cause**: No homes configured in Kwikset account

**Solutions**:
1. Open the Kwikset app
2. Create a new Home
3. Add your locks to the Home
4. Retry the integration setup

#### Locks not appearing after setup

**Cause**: Locks not assigned to the selected home

**Solutions**:
1. Open the Kwikset app
2. Verify locks are in the selected home
3. Wait 5 minutes for dynamic discovery
4. Use the "Reconfigure" option to trigger discovery

#### Lock shows "unavailable"

**Cause**: Communication issue with Kwikset cloud

**Solutions**:
1. Check if the lock is online in the Kwikset app
2. Verify the lock has good WiFi signal
3. Check lock battery level
4. Restart the integration

#### Actions fail with "Failed to lock/unlock"

**Cause**: API error or lock offline

**Solutions**:
1. Try the action in the Kwikset app
2. Check lock battery level
3. Verify lock WiFi connection
4. Check Home Assistant logs for details

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.kwikset: debug
    aiokwikset: debug
```

### Getting Help

1. Check the [GitHub Issues](https://github.com/explosivo22/kwikset-ha/issues) for known problems
2. Review Home Assistant logs for error details
3. Use the Diagnostics feature: **Settings** → **Devices & Services** → **Kwikset** → **Download Diagnostics**
4. Open a new issue with diagnostics file attached (sensitive data is automatically redacted)

---

## 📊 Quality Scale Compliance

This integration targets the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale) **Platinum tier**.

### Current Status: Gold ✅

| Tier | Status | Requirements Met |
|------|--------|------------------|
| **Bronze** | ✅ Complete | 9/9 |
| **Silver** | ✅ Complete | 8/8 |
| **Gold** | ✅ Complete | 9/9 |
| **Platinum** | 🔄 In Progress | 3/4 |

### Platinum Progress

| Requirement | Status | Notes |
|-------------|--------|-------|
| `async_dependency` | ✅ Done | aiokwikset is fully async |
| `runtime_data` | ✅ Done | Uses `KwiksetRuntimeData` dataclass |
| `strict_typing` | ✅ Done | `py.typed` marker, full annotations |
| `inject_websession` | ❌ Blocked | Requires upstream aiokwikset changes |

### Key Quality Features

- **Config Flow**: Full UI-based setup with MFA support
- **Reauthentication**: Automatic token refresh with reauth flow
- **Dynamic Discovery**: Automatic detection of new/removed devices
- **Stale Device Removal**: Cleanup of devices removed from account
- **Diagnostics**: Full diagnostic data with sensitive info redaction
- **Test Coverage**: Comprehensive pytest test suite
- **Type Safety**: Full type annotations with `py.typed` marker
- **Error Handling**: Proper exception handling with user-friendly messages

See [quality_scale.yaml](custom_components/kwikset-ha/quality_scale.yaml) for detailed compliance tracking.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest tests/`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/explosivo22/kwikset-ha.git
cd kwikset-ha

# Install dependencies
pip install -r requirements_test.txt

# Run tests
pytest tests/

# Run linting
ruff check custom_components/
```

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/explosivo22/kwikset-ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/explosivo22/kwikset-ha/discussions)
- **Buy Me a Coffee**: [Support Development](https://www.buymeacoffee.com/Explosivo22)

---

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This integration is not affiliated with, endorsed by, or connected to Kwikset or Spectrum Brands. Kwikset is a trademark of Spectrum Brands, Inc. This is an unofficial integration using an undocumented API that may change at any time