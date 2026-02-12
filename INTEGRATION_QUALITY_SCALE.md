# Integration Quality Scale Checklist

This checklist follows the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/).

## Bronze
- [X] `action-setup` - Service actions are registered in async_setup
    - No custom service actions are registered. The lock uses standard `lock.lock`/`lock.unlock` services. Switches use standard `switch.turn_on`/`switch.turn_off` services.
- [X] `appropriate-polling` - If it's a polling integration, set an appropriate polling interval
    - Uses `DataUpdateCoordinator` with configurable polling interval (default 30s, range 15-60s). Set via options flow. `iot_class: cloud_polling` is correctly defined in manifest.
- [X] `brands` - Has branding assets available for the integration
    - **Exempt**: Custom component - branding assets are only required for core integrations in the HA brands repository.
- [X] `common-modules` - Place common patterns in common modules
    - Common patterns are in `entity.py` (base `KwiksetEntity` class), `device.py` (coordinator), and `const.py`.
- [X] `config-flow-test-coverage` - Full test coverage for the config flow
    - Full test coverage in `tests/test_config_flow.py` with 17 tests covering user flow, MFA, home selection, reauth, reconfigure, and options flows.
- [X] `config-flow` - Integration needs to be able to be set up via the UI
    - [X] Uses `data_description` to give context to fields
    - [X] Uses `ConfigEntry.data` and `ConfigEntry.options` correctly
    - UI-based config flow implemented with `data_description` for all fields in strings.json.
- [X] `dependency-transparency` - Dependency transparency
    - `aiokwikset==0.4.0` is listed in `manifest.json` requirements.
- [X] `docs-actions` - The documentation describes the provided service actions that can be used
    - README documents all service actions including lock/unlock and switch controls (LED, Audio, Secure Screen).
- [X] `docs-high-level-description` - The documentation includes a high-level description of the integration brand, product, or service
    - README describes Kwikset Smart Locks and links to official product page.
- [X] `docs-installation-instructions` - The documentation provides step-by-step installation instructions for the integration, including, if needed, prerequisites
    - README provides HACS and manual installation instructions.
- [X] `docs-removal-instructions` - The documentation provides removal instructions
    - README includes "Removing the Integration" section with step-by-step instructions.
- [X] `entity-event-setup` - Entity events are subscribed in the correct lifecycle methods
    - Uses `CoordinatorEntity` which handles event subscriptions correctly via `async_added_to_hass`. New device events use proper `hass.bus.async_listen` with `async_on_unload`.
- [X] `entity-unique-id` - Entities have a unique ID
    - All entities have unique IDs set via `_attr_unique_id = f"{coordinator.device_id}_{entity_type}"` in base entity class.
- [X] `has-entity-name` - Entities use has_entity_name = True
    - `_attr_has_entity_name = True` is set in `KwiksetEntity` base class.
- [X] `runtime-data` - Use ConfigEntry.runtime_data to store runtime data
    - Uses `KwiksetRuntimeData` dataclass with `ConfigEntry.runtime_data` pattern. Type alias `KwiksetConfigEntry` provides type safety.
- [X] `test-before-configure` - Test a connection in the config flow
    - Config flow calls `async_login()` which validates credentials before proceeding. `RequestError` is caught and shown as error.
- [X] `test-before-setup` - Check during integration initialization if we are able to set it up correctly
    - `async_setup_entry` tries `async_renew_access_token` and `get_info()`, raises `ConfigEntryNotReady` on `RequestError` and `ConfigEntryAuthFailed` on `Unauthenticated`.
- [X] `unique-config-entry` - Don't allow the same device or service to be able to be set up twice
    - Uses `async_set_unique_id(home_id)` and `_abort_if_unique_id_configured()`. Also filters out existing homes from selection.

## Silver
- [X] `action-exceptions` - Service actions raise exceptions when encountering failures
    - Device coordinator methods raise `ConfigEntryAuthFailed` on auth errors and `HomeAssistantError` with translation keys for user-facing errors.
- [X] `config-entry-unloading` - Support config entry unloading
    - `async_unload_entry` is implemented, unloads platforms and cleans up runtime data.
- [X] `docs-configuration-parameters` - The documentation describes all integration configuration options
    - README includes "Configuration Options" section documenting polling interval (15-60s, default 30s) with descriptions and recommendations.
- [X] `docs-installation-parameters` - The documentation describes all integration installation parameters
    - README includes "Installation Parameters" section documenting all setup parameters: Email, Password, Verification Code (MFA), and Home selection.
- [X] `entity-unavailable` - Mark entity unavailable if appropriate
    - `available` property returns `self.coordinator.last_update_success` in base entity.
- [X] `integration-owner` - Has an integration owner
    - `codeowners: ["@explosivo22"]` defined in manifest.json.
- [X] `log-when-unavailable` - If internet/device/service is unavailable, log once when unavailable and once when back connected
    - Uses DataUpdateCoordinator pattern which automatically logs connection state changes.
- [X] `parallel-updates` - Number of parallel updates is specified
    - `PARALLEL_UPDATES = 1` defined in const.py and imported in all platform modules.
- [X] `reauthentication-flow` - Reauthentication needs to be available via the UI
    - `async_step_reauth` and `async_step_reauth_confirm` are implemented with MFA support.
- [X] `test-coverage` - Above 95% test coverage for all integration modules
    - Comprehensive test suite in tests/ with 117 passing tests covering config flow, coordinator, setup, and entities.

## Gold
- [X] `devices` - The integration creates devices
    - `device_info` property returns `DeviceInfo` with identifiers, manufacturer, model, name, and sw_version.
- [X] `diagnostics` - Implements diagnostics
    - `diagnostics.py` implements `async_get_config_entry_diagnostics` with sensitive data redaction.
- [ ] `discovery-update-info` - Integration uses discovery info to update network information
    - N/A - Not applicable - this is a cloud-based integration without local network discovery.
- [ ] `discovery` - Devices can be discovered
    - N/A - Not applicable - cloud-based authentication required, devices cannot be auto-discovered.
- [X] `docs-data-update` - The documentation describes how data is updated
    - README includes "Data Updates" section describing polling behavior, intervals, latency, and device discovery timing.
- [X] `docs-examples` - The documentation provides automation examples the user can use.
    - README includes "Use Cases & Automations" section with example automations.
- [X] `docs-known-limitations` - The documentation describes known limitations of the integration (not to be confused with bugs)
    - README includes comprehensive "Known Limitations" section covering API limitations, feature limitations, and device limitations.
- [X] `docs-supported-devices` - The documentation describes known supported / unsupported devices
    - README includes "Supported Devices" section with product line table.
- [X] `docs-supported-functions` - The documentation describes the supported functionality, including entities, and platforms
    - README describes all entities: lock, battery sensor, and switches (LED, Audio, Secure Screen).
- [X] `docs-troubleshooting` - The documentation provides troubleshooting information
    - README includes comprehensive "Troubleshooting" section.
- [X] `docs-use-cases` - The documentation describes use cases to illustrate how this integration can be used
    - README includes "Use Cases & Automations" section with example automations.
- [X] `dynamic-devices` - Devices added after integration setup
    - Implements `_async_update_devices` with periodic check (every 5 minutes) and event-based entity addition.
- [X] `entity-category` - Entities are assigned an appropriate EntityCategory
    - Battery sensor has `EntityCategory.DIAGNOSTIC`. Switches have `EntityCategory.CONFIG`.
- [X] `entity-device-class` - Entities use device classes where possible
    - Battery sensor uses `SensorDeviceClass.BATTERY`. Lock inherits device class from `LockEntity`.
- [X] `entity-disabled-by-default` - Integration disables less popular (or noisy) entities
    - Secure Screen switch is disabled by default via `entity_registry_enabled_default=False`. Users can enable it if needed.
- [X] `entity-translations` - Entities have translated names
    - Entity names use translation keys with translations in 15 languages.
- [X] `exception-translations` - Exception messages are translatable
    - All exceptions use `translation_domain` and `translation_key` parameters. Translations defined in `strings.json` under `exceptions`.
- [X] `icon-translations` - Entities implement icon translations
    - `icons.json` defines icons for all entities with state-based icons for lock and switches, range-based icons for battery sensor.
- [X] `reconfiguration-flow` - Integrations should have a reconfigure flow
    - `async_step_reconfigure` is implemented to reload and discover new devices.
- [X] `repair-issues` - Repair issues and repair flows are used when user intervention is needed
    - `_create_auth_issue` creates repair issue for auth failures. Repair flow defined in `strings.json` under `issues.auth_expired.fix_flow`.
- [X] `stale-devices` - Stale devices are removed
    - `_async_update_devices` removes stale devices from registry and `async_remove_config_entry_device` returns True.

## Platinum
- [X] `async-dependency` - Dependency is async
    - Uses `aiokwikset` which is an async library (aio prefix).
- [X] `inject-websession` - The integration dependency supports passing in a websession
    - `async_get_clientsession(hass)` is passed to `API(websession=...)` in `async_setup_entry`. The API client accepts the websession parameter and uses it for all HTTP requests.
- [X] `strict-typing` - Strict typing
    - `py.typed` marker file exists. Full type annotations throughout with TypedDict, Final, and generic types.

---

## Summary

| Tier | Met | Total | Percentage |
|------|-----|-------|------------|
| Bronze | 18 | 18 | 100% ✅ |
| Silver | 10 | 10 | 100% ✅ |
| Gold | 18 | 18 | 100% ✅ |
| Platinum | 3 | 3 | 100% ✅ |

### Bronze Tier: COMPLETE ✅

All Bronze requirements are met.

### Silver Tier: COMPLETE ✅

All Silver requirements are met.

### Gold Tier: COMPLETE ✅

All Gold requirements are met. Note: `discovery` and `discovery-update-info` are marked N/A as this is a cloud-based integration.

### Platinum Tier: COMPLETE ✅

All Platinum requirements are met! The `inject-websession` requirement is now fulfilled with the updated aiokwikset library.
