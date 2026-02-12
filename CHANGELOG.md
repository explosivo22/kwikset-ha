# Changelog

All notable changes to the Kwikset Smart Locks integration for Home Assistant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.4.0] - 2025-12-03

### ⚠️ BREAKING CHANGES

- **Folder Rename**: The integration folder has been renamed from `custom_components/kwikset-ha` to `custom_components/kwikset` to follow Home Assistant's domain naming conventions
  - **HACS cannot automatically upgrade** from v0.3.x to v0.4.0
  - **Manual migration required** - see [MIGRATION.md](MIGRATION.md) for detailed instructions
  - The old `kwikset-ha` folder must be manually deleted before installing v0.4.0
  - Your automations and entity IDs will continue to work after migration (domain is unchanged)

### Added
- **Migration Guide**: Comprehensive [MIGRATION.md](MIGRATION.md) with step-by-step upgrade instructions
- **Platinum Quality Scale**: Full platinum tier compliance achieved
  - `inject_websession`: Now passes Home Assistant's aiohttp session to the API client
- **Comprehensive CHANGELOG.md**: Full version history documentation
- **Enhanced README.md**: Complete documentation with breaking change notice

### Changed
- **Folder Structure**: `custom_components/kwikset-ha/` → `custom_components/kwikset/`
- **Quality Scale**: Updated from Gold to Platinum tier
- **aiokwikset**: Updated to version 0.4.0 with websession injection support

### Fixed
- Domain and folder name mismatch that could cause issues with future Home Assistant updates

---

## [0.3.5] - 2025-01-15

### Added
- **Platinum Quality Scale Compliance**: Full architectural refactor for platinum tier
  - `runtime_data` pattern with typed `KwiksetRuntimeData` dataclass
  - `py.typed` marker for strict typing compliance
  - Comprehensive type annotations throughout
- **Proactive Token Refresh**: JWT tokens are now refreshed 5 minutes before expiry
  - Prevents authentication failures during normal operations
  - Tokens are parsed to extract expiration time
  - Refreshed tokens are persisted to config entry
- **Retry Logic**: All API operations now have retry logic
  - `MAX_RETRY_ATTEMPTS = 3` with exponential backoff
  - `RETRY_DELAY_SECONDS = 2` between retries
  - Proper error categorization (auth vs transient)
- **Stale Device Tracking**: Automatic removal of devices that disappear from account
  - `known_devices` tracking in `KwiksetRuntimeData`
  - Devices removed from API are removed from device registry
- **Dynamic Device Discovery**: New devices are automatically discovered
  - 5-minute periodic polling for new/removed devices
  - Bus events notify platforms of new devices
  - No integration reload required
- **Reconfigure Flow**: Trigger device discovery without full re-setup
- **Translation Key Support**: All entities use `_attr_translation_key` for localization
- **Comprehensive Diagnostics**: Full diagnostic data with sensitive info redaction

### Changed
- Migrated from `hass.data[DOMAIN]` to `entry.runtime_data` pattern
- Entities now use `CoordinatorEntity` base class
- All API calls routed through coordinator with retry logic
- Switch entities use entity descriptions for data-driven approach
- Improved error handling with `HomeAssistantError` and translation keys

### Fixed
- Token persistence across Home Assistant restarts
- Race conditions in concurrent API calls
- Entity unavailability detection via coordinator status

---

## [0.3.4] - 2024-12-01

### Added
- Multi-Factor Authentication (MFA) support in config flow
  - Software token (authenticator app) support
  - SMS verification support
  - MFA support during reauthentication
- Options flow for configurable polling interval (15-60 seconds)
- Config entry migrations (version 1 → 4)

### Changed
- Default polling interval changed from 60s to 30s
- Moved refresh interval from `entry.data` to `entry.options`

### Fixed
- Duplicate config entries for same home
- Token refresh failing after HA restart

---

## [0.3.3] - 2024-11-01

### Added
- Reauthentication flow for expired tokens
- Battery sensor with diagnostic category
- LED, Audio, and Secure Screen switches
- `PARALLEL_UPDATES = 1` to prevent API rate limiting

### Changed
- Improved entity naming with `_attr_has_entity_name = True`
- Better error messages in config flow

---

## [0.3.2] - 2024-10-01

### Added
- Support for multiple Kwikset homes
- Home selection step in config flow
- Device registry integration with proper identifiers

### Changed
- Config entry unique_id now uses home_id
- Improved logging throughout

---

## [0.3.1] - 2024-09-01

### Fixed
- API connection handling improvements
- Better error recovery on network failures

---

## [0.3.0] - 2024-08-01

### Added
- Initial async refactor using `aiokwikset` library
- DataUpdateCoordinator pattern for device polling
- Basic lock/unlock functionality
- HACS custom repository support

### Changed
- Complete rewrite from synchronous to asynchronous architecture
- Migrated from requests to aiohttp via aiokwikset

---

## [0.2.x] - 2024-01-01 to 2024-07-01

### Note
Legacy versions using synchronous API calls. Not recommended for use.

---

## [0.1.x] - 2023-01-01 to 2023-12-31

### Note
Initial development versions. Proof of concept only.

---

## Fork History

This integration was originally created by [@explosivo22](https://github.com/explosivo22) as a custom component for Home Assistant to control Kwikset smart locks via the unofficial cloud API.

### Key Milestones

| Date | Version | Milestone |
|------|---------|-----------|
| 2023 | 0.1.x | Initial development and proof of concept |
| 2024 | 0.2.x | Basic functionality with synchronous API |
| 2024-08 | 0.3.0 | Complete async rewrite with aiokwikset library |
| 2024-10 | 0.3.2 | Multi-home support |
| 2024-11 | 0.3.3 | Platform expansion (sensors, switches) |
| 2024-12 | 0.3.4 | MFA support and options flow |
| 2025-01 | 0.3.5 | Platinum Quality Scale compliance |

### Contributors

- [@explosivo22](https://github.com/explosivo22) - Original author and maintainer

---

## Quality Scale Progression

| Tier | Status | Date Achieved |
|------|--------|---------------|
| Bronze | ✅ Complete | 2024-08 |
| Silver | ✅ Complete | 2024-11 |
| Gold | ✅ Complete | 2024-12 |
| Platinum | 🔄 In Progress | - |

### Platinum Blockers

1. **`inject_websession`**: The `aiokwikset` library creates its own `aiohttp.ClientSession` internally. Achieving full platinum compliance requires upstream library modification to accept a session parameter.

---

[Unreleased]: https://github.com/explosivo22/kwikset-ha/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.5...v0.4.0
[0.3.5]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/explosivo22/kwikset-ha/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/explosivo22/kwikset-ha/releases/tag/v0.3.0
