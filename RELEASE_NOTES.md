# Release Notes — v0.6.3

## 🐛 Bug Fixes

### Lock State Transitions (#119, fixes #118)
- **Optimistic lock/unlock state no longer briefly reverts** to the prior state before reflecting the new state
- The optimistic state timer now only resets when the expected target state is confirmed by a coordinator update, preventing a flash of the old state

### Startup Performance — No Longer Blocks Home Assistant Setup
- **WebSocket subscription now runs as a background task** instead of blocking `async_setup_entry`
- **History fetch is deferred** to the second poll cycle — the first coordinator refresh only fetches device info, eliminating 30–60s+ startup delays when the Kwikset API is slow to respond
- This resolves `Waiting for integrations to complete setup: kwikset` warnings in HA logs

### Event Entity — No Spurious Firing on Startup
- **Lock event entity no longer fires a false event** when loading history data for the first time after HA restart or integration reload
- First history arrival now seeds the event ID without triggering `_trigger_event()`, preventing phantom automation triggers

### Diagnostic History Sensors — No State Changes on Startup
- **Last Lock Event, User, Method, and Category sensors** no longer produce `state_changed` events when the integration loads
- These sensors now extend `RestoreEntity` to restore their previous state and attributes from the last HA run
- Live coordinator data only takes over once the history fetch completes, preventing `unknown → value` transitions and attribute flicker

## 🧪 Testing

- **418 tests** — all passing
- Updated coordinator history tests to account for deferred history fetch (second refresh required)
- Added WebSocket background task patching fixtures to E2E and setup tests
- New lock state transition tests for optimistic state reset logic
- Expanded history sensor tests covering RestoreEntity behavior and attribute caching

## 📊 Stats

- **10 files changed** | **354 insertions** | **114 deletions**

---

**Full Changelog**: https://github.com/explosivo22/kwikset-ha/compare/0.6.1...0.6.3

---

# Release Notes — v0.6.1

## ⚠️ Breaking Changes

- **Dependency upgrade**: `aiokwikset` bumped from `0.4.0` to `0.6.1`
- **IoT class changed**: `cloud_polling` → `cloud_push` (reflects new WebSocket real-time push support)

## ✨ New Features

### Access Code Management (7 new services)
- **`kwikset.create_access_code`** — Create access codes with optional scheduling (time-limited, recurring, or custom day-of-week)
- **`kwikset.edit_access_code`** — Edit existing access codes and their schedules
- **`kwikset.disable_access_code`** — Disable an access code by slot number
- **`kwikset.enable_access_code`** — Re-enable a previously disabled access code
- **`kwikset.delete_access_code`** — Delete a single access code by slot
- **`kwikset.delete_all_access_codes`** — Delete all access codes from a lock
- **`kwikset.list_access_codes`** — List all access codes with slot assignments
- Persistent tracking via Home Assistant storage for HA-managed codes
- Minimum code length enforcement (4+ digits)

### Home User Management (4 new services)
- **`kwikset.invite_user`** — Invite users to the Kwikset home with customizable access times
- **`kwikset.update_user`** — Update user access permissions and time restrictions
- **`kwikset.delete_user`** — Remove a user from the home
- **`kwikset.list_users`** — List all home users with their roles and access details

### WebSocket Real-Time Events
- **Real-time push updates** via Kwikset WebSocket subscription — lock/unlock events arrive instantly instead of waiting for the next poll cycle
- **Automatic polling reduction** — polling interval increases to 900s heartbeat when WebSocket is active, reducing API load
- **Graceful fallback** — automatically reverts to normal polling if WebSocket connection fails
- **Nested payload handling** — properly unwraps nested WebSocket event payloads

### Lock Event Entity (`event` platform)
- **`event.kwikset_lock_event`** — fires `locked`, `unlocked`, and `jammed` events detected via coordinator history polling
- Includes event attributes: user, method, timestamp
- Full logbook support and automation trigger compatibility

### New Sensors
- **Last Lock Event** — shows the most recent lock/unlock/jammed event
- **Last Lock User** — identifies who performed the last lock action
- **Last Lock Method** — shows how the lock was operated (keypad, app, auto-lock, etc.)
- **Last Lock Category** — categorizes the event type
- **Access Code Count** — number of active access codes with per-slot details in attributes
- **Home User Count** — number of users with access to the Kwikset home

### Device History
- Coordinator now fetches and exposes device history events
- History-based sensors automatically update when door status changes

### Config Flow Enhancements
- **Auto-relogin** — stored passwords enable automatic re-authentication when tokens expire
- Enhanced diagnostics with stored password redaction

## 🛡️ Reliability & Error Handling

- Door status change detection triggers automatic history refresh via debouncer
- Real-time event data merges with coordinator state (null values in events don't overwrite existing data)
- Proper error handling for all 11 services with translated exception messages
- WebSocket subscription lifecycle tied to config entry for clean teardown

## 🔧 Code Quality

- New `event.py` platform module for lock event entities
- New `services.py` module (1,050+ lines) with full service infrastructure
- New `services.yaml` with HA UI selectors for all service parameters
- Refactored coordinator with access code tracking, slot parsing, and WebSocket event handling
- All service handlers accept `HomeAssistant` instance for proper dependency injection

## 🌐 Translations

- All 15 languages updated with strings for 11 new services, new sensors, event entities, and error messages
- Languages: de, en, es, fr, it, ja, ko, nl, pl, pt-BR, pt, ru, sv, zh-Hans, zh-Hant

## 🧪 Testing

- **415 tests** — all passing
- New `test_services.py` with 30+ tests covering all access code and user management services
- New `test_entity_platforms.py` with comprehensive entity value and description tests
- Expanded `test_setup_entry.py` with WebSocket subscription tests (connection, events, nested payloads, unknown devices, cleanup)
- Expanded `test_device_coordinator.py` with history, access code, and real-time event handling tests
- Expanded `test_config_flow.py` with auto-relogin and new flow path tests

## 🏗️ CI/CD

- Workflow scoped to `main` branch only — pushes to `dev` no longer trigger duplicate CI runs
- Pull requests targeting `main` still run full validation

## 📊 Stats

- **36 files changed** | **16,590 insertions** | **214 deletions**

---

**Full Changelog**: https://github.com/explosivo22/kwikset-ha/compare/0.4.2...0.6.1
