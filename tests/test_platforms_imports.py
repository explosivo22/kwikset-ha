"""Tests for platform module imports and structure.

Tests the module-level structure and imports of all platform files including:
- Correct PARALLEL_UPDATES value
- Required function exports (async_setup_entry)
- Platform-specific constants and classes
- EntityDescription exports
- TYPE_CHECKING imports

Quality Scale: Bronze tier - ensures platform modules are structured correctly.

Note: This module uses functions instead of class methods with direct imports
to ensure tests are isolated and lazily load modules.

Some tests are marked with pytest.importorskip for modules that use Home Assistant
APIs not available in all versions (e.g., AddConfigEntryEntitiesCallback).
"""

from __future__ import annotations

import pytest


def _can_import_lock_module() -> bool:
    """Check if lock module can be imported (requires AddConfigEntryEntitiesCallback)."""
    try:
        from custom_components.kwikset import lock  # noqa: F401

        return True
    except ImportError:
        return False


def _can_import_switch_module() -> bool:
    """Check if switch module can be imported (requires AddConfigEntryEntitiesCallback)."""
    try:
        from custom_components.kwikset import switch  # noqa: F401

        return True
    except ImportError:
        return False


# Skip reasons for API compatibility
LOCK_SKIP_REASON = "lock module requires AddConfigEntryEntitiesCallback (HA 2025.2+)"
SWITCH_SKIP_REASON = (
    "switch module requires AddConfigEntryEntitiesCallback (HA 2025.2+)"
)


# =============================================================================
# Lock Platform Import Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_lock_module(), reason=LOCK_SKIP_REASON)
class TestLockPlatformImports:
    """Tests for lock platform module structure."""

    def test_lock_module_imports(self) -> None:
        """Test lock module can be imported without errors."""
        from custom_components.kwikset import lock

        assert lock is not None

    def test_lock_has_async_setup_entry(self) -> None:
        """Test lock module exports async_setup_entry."""
        from custom_components.kwikset import lock

        assert hasattr(lock, "async_setup_entry")
        assert callable(lock.async_setup_entry)

    def test_lock_parallel_updates_value(self) -> None:
        """Test lock module has PARALLEL_UPDATES = 1."""
        from custom_components.kwikset import lock

        assert hasattr(lock, "PARALLEL_UPDATES")
        assert lock.PARALLEL_UPDATES == 1

    def test_lock_has_kwikset_lock_class(self) -> None:
        """Test lock module exports KwiksetLock class."""
        from custom_components.kwikset.lock import KwiksetLock

        assert KwiksetLock is not None

    def test_lock_inherits_from_lock_entity(self) -> None:
        """Test KwiksetLock inherits from LockEntity."""
        from homeassistant.components.lock import LockEntity

        from custom_components.kwikset.lock import KwiksetLock

        assert issubclass(KwiksetLock, LockEntity)


# =============================================================================
# Sensor Platform Import Tests
# =============================================================================


class TestSensorPlatformImports:
    """Tests for sensor platform module structure."""

    def test_sensor_module_imports(self) -> None:
        """Test sensor module can be imported without errors."""
        from custom_components.kwikset import sensor

        assert sensor is not None

    def test_sensor_has_async_setup_entry(self) -> None:
        """Test sensor module exports async_setup_entry."""
        from custom_components.kwikset import sensor

        assert hasattr(sensor, "async_setup_entry")
        assert callable(sensor.async_setup_entry)

    def test_sensor_parallel_updates_value(self) -> None:
        """Test sensor module has PARALLEL_UPDATES = 1."""
        from custom_components.kwikset import sensor

        assert hasattr(sensor, "PARALLEL_UPDATES")
        assert sensor.PARALLEL_UPDATES == 1

    def test_sensor_has_kwikset_sensor_class(self) -> None:
        """Test sensor module exports KwiksetSensor class."""
        from custom_components.kwikset.sensor import KwiksetSensor

        assert KwiksetSensor is not None

    def test_sensor_inherits_from_sensor_entity(self) -> None:
        """Test KwiksetSensor inherits from SensorEntity."""
        from homeassistant.components.sensor import SensorEntity

        from custom_components.kwikset.sensor import KwiksetSensor

        assert issubclass(KwiksetSensor, SensorEntity)

    def test_sensor_has_entity_descriptions(self) -> None:
        """Test sensor module exports SENSOR_DESCRIPTIONS."""
        from custom_components.kwikset.sensor import SENSOR_DESCRIPTIONS

        assert SENSOR_DESCRIPTIONS is not None
        assert isinstance(SENSOR_DESCRIPTIONS, tuple)
        assert len(SENSOR_DESCRIPTIONS) > 0

    def test_sensor_has_entity_description_class(self) -> None:
        """Test sensor module exports KwiksetSensorEntityDescription."""
        from custom_components.kwikset.sensor import KwiksetSensorEntityDescription

        assert KwiksetSensorEntityDescription is not None


# =============================================================================
# Switch Platform Import Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_switch_module(), reason=SWITCH_SKIP_REASON)
class TestSwitchPlatformImports:
    """Tests for switch platform module structure."""

    def test_switch_module_imports(self) -> None:
        """Test switch module can be imported without errors."""
        from custom_components.kwikset import switch

        assert switch is not None

    def test_switch_has_async_setup_entry(self) -> None:
        """Test switch module exports async_setup_entry."""
        from custom_components.kwikset import switch

        assert hasattr(switch, "async_setup_entry")
        assert callable(switch.async_setup_entry)

    def test_switch_parallel_updates_value(self) -> None:
        """Test switch module has PARALLEL_UPDATES = 1."""
        from custom_components.kwikset import switch

        assert hasattr(switch, "PARALLEL_UPDATES")
        assert switch.PARALLEL_UPDATES == 1

    def test_switch_has_kwikset_switch_class(self) -> None:
        """Test switch module exports KwiksetSwitch class."""
        from custom_components.kwikset.switch import KwiksetSwitch

        assert KwiksetSwitch is not None

    def test_switch_inherits_from_switch_entity(self) -> None:
        """Test KwiksetSwitch inherits from SwitchEntity."""
        from homeassistant.components.switch import SwitchEntity

        from custom_components.kwikset.switch import KwiksetSwitch

        assert issubclass(KwiksetSwitch, SwitchEntity)

    def test_switch_has_entity_descriptions(self) -> None:
        """Test switch module exports SWITCH_DESCRIPTIONS."""
        from custom_components.kwikset.switch import SWITCH_DESCRIPTIONS

        assert SWITCH_DESCRIPTIONS is not None
        assert isinstance(SWITCH_DESCRIPTIONS, tuple)
        assert len(SWITCH_DESCRIPTIONS) == 3

    def test_switch_has_entity_description_class(self) -> None:
        """Test switch module exports KwiksetSwitchEntityDescription."""
        from custom_components.kwikset.switch import KwiksetSwitchEntityDescription

        assert KwiksetSwitchEntityDescription is not None


# =============================================================================
# Entity Base Module Import Tests
# =============================================================================


class TestEntityModuleImports:
    """Tests for entity base module structure."""

    def test_entity_module_imports(self) -> None:
        """Test entity module can be imported without errors."""
        from custom_components.kwikset import entity

        assert entity is not None

    def test_entity_has_kwikset_entity_class(self) -> None:
        """Test entity module exports KwiksetEntity class."""
        from custom_components.kwikset.entity import KwiksetEntity

        assert KwiksetEntity is not None

    def test_entity_inherits_from_coordinator_entity(self) -> None:
        """Test KwiksetEntity inherits from CoordinatorEntity."""
        from homeassistant.helpers.update_coordinator import CoordinatorEntity

        from custom_components.kwikset.entity import KwiksetEntity

        assert issubclass(KwiksetEntity, CoordinatorEntity)


# =============================================================================
# Device Coordinator Module Import Tests
# =============================================================================


class TestDeviceModuleImports:
    """Tests for device coordinator module structure."""

    def test_device_module_imports(self) -> None:
        """Test device module can be imported without errors."""
        from custom_components.kwikset import device

        assert device is not None

    def test_device_has_coordinator_class(self) -> None:
        """Test device module exports KwiksetDeviceDataUpdateCoordinator."""
        from custom_components.kwikset.device import KwiksetDeviceDataUpdateCoordinator

        assert KwiksetDeviceDataUpdateCoordinator is not None

    def test_coordinator_inherits_from_data_update_coordinator(self) -> None:
        """Test coordinator inherits from DataUpdateCoordinator."""
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.kwikset.device import KwiksetDeviceDataUpdateCoordinator

        assert issubclass(KwiksetDeviceDataUpdateCoordinator, DataUpdateCoordinator)


# =============================================================================
# Constants Module Import Tests
# =============================================================================


class TestConstantsModuleImports:
    """Tests for constants module structure."""

    def test_constants_module_imports(self) -> None:
        """Test constants module can be imported without errors."""
        from custom_components.kwikset import const

        assert const is not None

    def test_constants_has_domain(self) -> None:
        """Test constants module exports DOMAIN."""
        from custom_components.kwikset.const import DOMAIN

        assert DOMAIN == "kwikset"

    def test_constants_has_parallel_updates(self) -> None:
        """Test constants module exports PARALLEL_UPDATES."""
        from custom_components.kwikset.const import PARALLEL_UPDATES

        assert PARALLEL_UPDATES == 1

    def test_constants_has_conf_keys(self) -> None:
        """Test constants module exports configuration keys."""
        from custom_components.kwikset.const import CONF_ACCESS_TOKEN
        from custom_components.kwikset.const import CONF_HOME_ID
        from custom_components.kwikset.const import CONF_REFRESH_INTERVAL
        from custom_components.kwikset.const import CONF_REFRESH_TOKEN

        assert CONF_ACCESS_TOKEN is not None
        assert CONF_HOME_ID is not None
        assert CONF_REFRESH_INTERVAL is not None
        assert CONF_REFRESH_TOKEN is not None

    def test_constants_has_defaults(self) -> None:
        """Test constants module exports default values."""
        from custom_components.kwikset.const import DEFAULT_REFRESH_INTERVAL
        from custom_components.kwikset.const import MAX_RETRY_ATTEMPTS
        from custom_components.kwikset.const import RETRY_DELAY_SECONDS

        assert DEFAULT_REFRESH_INTERVAL == 30
        assert MAX_RETRY_ATTEMPTS == 3
        assert RETRY_DELAY_SECONDS == 2

    def test_constants_has_logger(self) -> None:
        """Test constants module exports LOGGER."""
        from custom_components.kwikset.const import LOGGER

        assert LOGGER is not None


# =============================================================================
# Config Flow Module Import Tests
# =============================================================================


class TestConfigFlowModuleImports:
    """Tests for config flow module structure."""

    def test_config_flow_module_imports(self) -> None:
        """Test config_flow module can be imported without errors."""
        from custom_components.kwikset import config_flow

        assert config_flow is not None

    def test_config_flow_has_handler_class(self) -> None:
        """Test config_flow module exports KwiksetFlowHandler."""
        from custom_components.kwikset.config_flow import KwiksetFlowHandler

        assert KwiksetFlowHandler is not None

    def test_config_flow_has_options_flow(self) -> None:
        """Test config_flow module exports KwiksetOptionsFlow."""
        from custom_components.kwikset.config_flow import KwiksetOptionsFlow

        assert KwiksetOptionsFlow is not None

    def test_config_flow_handler_version(self) -> None:
        """Test config flow handler has version 5."""
        from custom_components.kwikset.config_flow import KwiksetFlowHandler

        assert KwiksetFlowHandler.VERSION == 5


# =============================================================================
# Main Init Module Import Tests
# =============================================================================


class TestInitModuleImports:
    """Tests for main __init__ module structure."""

    def test_init_module_imports(self) -> None:
        """Test __init__ module can be imported without errors."""
        import custom_components.kwikset

        assert custom_components.kwikset is not None

    def test_init_has_async_setup_entry(self) -> None:
        """Test __init__ exports async_setup_entry."""
        from custom_components.kwikset import async_setup_entry

        assert async_setup_entry is not None
        assert callable(async_setup_entry)

    def test_init_has_async_unload_entry(self) -> None:
        """Test __init__ exports async_unload_entry."""
        from custom_components.kwikset import async_unload_entry

        assert async_unload_entry is not None
        assert callable(async_unload_entry)

    def test_init_has_async_migrate_entry(self) -> None:
        """Test __init__ exports async_migrate_entry."""
        from custom_components.kwikset import async_migrate_entry

        assert async_migrate_entry is not None
        assert callable(async_migrate_entry)

    def test_init_has_runtime_data_class(self) -> None:
        """Test __init__ exports KwiksetRuntimeData."""
        from custom_components.kwikset import KwiksetRuntimeData

        assert KwiksetRuntimeData is not None

    def test_init_has_platforms_list(self) -> None:
        """Test __init__ exports PLATFORMS list."""
        from custom_components.kwikset import PLATFORMS

        assert PLATFORMS is not None
        assert len(PLATFORMS) == 3


# =============================================================================
# Cross-Module Consistency Tests
# =============================================================================


class TestCrossModuleConsistency:
    """Tests for consistency across modules."""

    @pytest.mark.skipif(
        not _can_import_lock_module() or not _can_import_switch_module(),
        reason="Requires lock and switch modules (HA 2025.2+)",
    )
    def test_all_platforms_use_same_parallel_updates(self) -> None:
        """Test all platform modules use the same PARALLEL_UPDATES value."""
        from custom_components.kwikset.const import PARALLEL_UPDATES as CONST_VALUE
        from custom_components.kwikset.lock import PARALLEL_UPDATES as LOCK_VALUE
        from custom_components.kwikset.sensor import PARALLEL_UPDATES as SENSOR_VALUE
        from custom_components.kwikset.switch import PARALLEL_UPDATES as SWITCH_VALUE

        assert LOCK_VALUE == CONST_VALUE
        assert SENSOR_VALUE == CONST_VALUE
        assert SWITCH_VALUE == CONST_VALUE

    @pytest.mark.skipif(
        not _can_import_lock_module() or not _can_import_switch_module(),
        reason="Requires lock and switch modules (HA 2025.2+)",
    )
    def test_all_entities_inherit_from_kwikset_entity(self) -> None:
        """Test all entity classes inherit from KwiksetEntity."""
        from custom_components.kwikset.entity import KwiksetEntity
        from custom_components.kwikset.lock import KwiksetLock
        from custom_components.kwikset.sensor import KwiksetSensor
        from custom_components.kwikset.switch import KwiksetSwitch

        assert issubclass(KwiksetLock, KwiksetEntity)
        assert issubclass(KwiksetSensor, KwiksetEntity)
        assert issubclass(KwiksetSwitch, KwiksetEntity)

    def test_domain_is_consistent(self) -> None:
        """Test DOMAIN is consistent across modules."""
        from custom_components.kwikset.const import DOMAIN

        assert DOMAIN == "kwikset"
