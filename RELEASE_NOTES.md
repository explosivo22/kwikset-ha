## ⚠️ Breaking Changes

- **Folder rename**: Integration directory renamed from `kwikset_ha` → `kwikset`. You **must** remove the old `custom_components/kwikset_ha/` folder before upgrading. See the [Migration Guide](https://github.com/explosivo22/kwikset-ha/blob/main/MIGRATION.md) for step-by-step instructions.
- **Dependency upgrade**: `aiokwikset` bumped to `0.4.0`

## ✨ Features

- **Optimistic state updates** for lock/unlock actions — immediate UI feedback with 30s timeout handling
- **Jammed state detection** — lock now properly reports "Jammed" status
- **Assumed state for switches** — LED, audio, and secure screen switches reflect cloud-based nature
- **Token management improvements** — better token refresh handling and error recovery
- **Authentication expiry handling** — user notifications when credentials expire, automatic reauth triggers
- **Enhanced diagnostics** — `id_token` added to redaction for privacy; quality scale set to platinum
- **Icon definitions** — custom icon mappings for all entities

## 🛡️ Reliability & Error Handling

- Improved API call retry logic with better error management
- Translation keys for all exceptions (translatable error messages)
- Reauth flow triggered automatically on authentication failures
- Coordinator logs errors once on failure and once on recovery

## 🔧 Code Quality

- Adopted `_attr_` pattern for cached entity properties
- `EntityDescription` pattern with `value_fn` lambdas for sensors and switches
- `KwiksetRuntimeData` dataclass with typed `KwiksetConfigEntry` alias
- Full type annotations with `TYPE_CHECKING` guards and `typing.Final` constants
- `__slots__` on entity classes for memory efficiency
- Dynamic device discovery via bus events with stale device removal

## 🌐 Translations

- Updated reauthentication descriptions across all 15 supported languages
- Refreshed entity descriptions and translations for consistency

## 🧪 Testing

- Comprehensive test suite covering config flow, coordinator, e2e, entity platforms, setup entry, and platform imports
- Mock API infrastructure with `async_get_clientsession` patching
- Tests for optimistic timeout behavior, jammed state, and switch assumed state

## 🏗️ CI/CD

- Enhanced CI workflow with linting (ruff), type checking (mypy), and automated test jobs
- Validation workflow for HACS and hassfest
- Bug report and feature request issue templates

## 📖 Documentation

- [Migration guide](https://github.com/explosivo22/kwikset-ha/blob/main/MIGRATION.md) for upgrading from v0.3.x
- README updated with installation, configuration, automation examples, troubleshooting, and known limitations
- Integration Quality Scale tracking (targeting Platinum)

## 📊 Stats

- **64 files changed** | **11,813 insertions** | **1,455 deletions**

---

**Full Changelog**: https://github.com/explosivo22/kwikset-ha/compare/0.3.5...0.4.0
