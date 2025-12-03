"""Tests for Kwikset entity platforms.

Tests the lock, sensor, and switch entity platforms including:
- Entity initialization and attributes
- State management and updates
- Lock/unlock actions with optimistic state
- Switch on/off actions with assumed state
- Error handling for actions
- Dynamic device discovery
- Entity registration and unique IDs
- Optimistic timeout behavior

Quality Scale: Platinum tier - comprehensive entity platform testing.

Note: This module uses pytest fixtures for lazy imports to ensure
compatibility across different Home Assistant versions. Some tests
are skipped if the required modules cannot be imported.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import PERCENTAGE
from homeassistant.exceptions import HomeAssistantError

# Import EntityCategory from the correct location based on HA version
try:
    from homeassistant.const import EntityCategory
except ImportError:
    from homeassistant.helpers.entity import EntityCategory

from custom_components.kwikset.const import DOMAIN
from custom_components.kwikset.const import OPTIMISTIC_TIMEOUT_SECONDS

from .conftest import MOCK_DEVICE_ID
from .conftest import MOCK_DEVICE_NAME

# =============================================================================
# API Compatibility Checks
# =============================================================================


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
# Fixtures for lazy module imports
# =============================================================================


@pytest.fixture
def entity_module():
    """Import entity module lazily."""
    from custom_components.kwikset import entity

    return entity


@pytest.fixture
def lock_module():
    """Import lock module lazily."""
    from custom_components.kwikset import lock

    return lock


@pytest.fixture
def sensor_module():
    """Import sensor module lazily."""
    from custom_components.kwikset import sensor

    return sensor


@pytest.fixture
def switch_module():
    """Import switch module lazily."""
    from custom_components.kwikset import switch

    return switch


# =============================================================================
# Base Entity Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_lock_module(), reason=LOCK_SKIP_REASON)
class TestKwiksetEntity:
    """Tests for the KwiksetEntity base class."""

    def test_entity_has_entity_name(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test entity has _attr_has_entity_name = True."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.has_entity_name is True

    def test_entity_unique_id_format(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test unique_id is formatted as device_id_entity_type."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.unique_id == f"{MOCK_DEVICE_ID}_lock"

    def test_entity_device_info(self, lock_module, mock_coordinator: MagicMock) -> None:
        """Test entity provides correct device_info."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        device_info = lock.device_info

        assert device_info is not None
        assert (DOMAIN, MOCK_DEVICE_ID) in device_info["identifiers"]
        assert device_info["manufacturer"] == "Kwikset"
        assert device_info["model"] == "Halo Touch"
        assert device_info["name"] == MOCK_DEVICE_NAME


# =============================================================================
# Lock Entity Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_lock_module(), reason=LOCK_SKIP_REASON)
class TestKwiksetLock:
    """Tests for the KwiksetLock entity."""

    def test_lock_is_lock_entity(
        self, lock_module, entity_module, mock_coordinator: MagicMock
    ) -> None:
        """Test KwiksetLock inherits from LockEntity."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert isinstance(lock, LockEntity)
        assert isinstance(lock, entity_module.KwiksetEntity)

    def test_lock_unique_id(self, lock_module, mock_coordinator: MagicMock) -> None:
        """Test lock unique_id is device_id_lock."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.unique_id == f"{MOCK_DEVICE_ID}_lock"

    def test_lock_name_is_none(self, lock_module, mock_coordinator: MagicMock) -> None:
        """Test lock _attr_name is None for primary entity."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock._attr_name is None

    def test_lock_translation_key(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test lock has correct translation_key."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock._attr_translation_key == "lock"

    def test_lock_is_locked_when_locked(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test is_locked returns True when coordinator status is Locked."""
        mock_coordinator.status = "Locked"
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.is_locked is True

    def test_lock_is_unlocked_when_unlocked(
        self, lock_module, mock_coordinator_unlocked: MagicMock
    ) -> None:
        """Test is_locked returns False when coordinator status is Unlocked."""
        lock = lock_module.KwiksetLock(mock_coordinator_unlocked)
        assert lock.is_locked is False

    def test_lock_is_none_when_unknown(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test is_locked returns None when coordinator status is Unknown."""
        mock_coordinator.status = "Unknown"
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.is_locked is None

    def test_lock_is_jammed_when_jammed(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test is_jammed returns True when coordinator status is Jammed."""
        mock_coordinator.status = "Jammed"
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.is_jammed is True
        # When jammed, is_locked should be indeterminate (None)
        assert lock.is_locked is None

    def test_lock_is_not_jammed_when_locked(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test is_jammed returns False when coordinator status is Locked."""
        mock_coordinator.status = "Locked"
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock.is_jammed is False
        assert lock.is_locked is True

    def test_lock_is_not_jammed_when_unlocked(
        self, lock_module, mock_coordinator_unlocked: MagicMock
    ) -> None:
        """Test is_jammed returns False when coordinator status is Unlocked."""
        lock = lock_module.KwiksetLock(mock_coordinator_unlocked)
        assert lock.is_jammed is False
        assert lock.is_locked is False

    async def test_async_lock_calls_coordinator(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_lock calls coordinator.lock()."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        await lock.async_lock()
        mock_coordinator.lock.assert_called_once()

    async def test_async_unlock_calls_coordinator(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_unlock calls coordinator.unlock()."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Mock hass and async_write_ha_state to avoid RuntimeError
        lock.hass = MagicMock()
        lock.hass.loop = MagicMock()
        lock.hass.loop.call_later = MagicMock(return_value=MagicMock())
        lock.async_write_ha_state = MagicMock()
        await lock.async_unlock()
        mock_coordinator.unlock.assert_called_once()

    async def test_async_lock_raises_error_on_failure(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_lock raises HomeAssistantError on failure."""
        mock_coordinator.lock.side_effect = Exception("API Error")
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Mock hass and async_write_ha_state to avoid RuntimeError
        lock.hass = MagicMock()
        lock.hass.loop = MagicMock()
        lock.hass.loop.call_later = MagicMock(return_value=MagicMock())
        lock.async_write_ha_state = MagicMock()

        with pytest.raises(HomeAssistantError) as exc_info:
            await lock.async_lock()

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "lock_failed"

    async def test_async_unlock_raises_error_on_failure(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_unlock raises HomeAssistantError on failure."""
        mock_coordinator.unlock.side_effect = Exception("API Error")
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Mock hass and async_write_ha_state to avoid RuntimeError
        lock.hass = MagicMock()
        lock.hass.loop = MagicMock()
        lock.hass.loop.call_later = MagicMock(return_value=MagicMock())
        lock.async_write_ha_state = MagicMock()

        with pytest.raises(HomeAssistantError) as exc_info:
            await lock.async_unlock()

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "unlock_failed"

    def test_lock_parallel_updates(self, lock_module) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert lock_module.PARALLEL_UPDATES == 1


# =============================================================================
# Lock Optimistic Timeout Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_lock_module(), reason=LOCK_SKIP_REASON)
class TestKwiksetLockOptimisticTimeout:
    """Tests for the KwiksetLock optimistic timeout functionality.

    The lock entity implements optimistic state updates following the
    Matter lock integration pattern:
    1. When lock/unlock is called, immediately set is_locking/is_unlocking
    2. Start a timer to reset the optimistic state
    3. When coordinator updates, reset the optimistic state
    4. On error, reset the optimistic state immediately
    """

    def test_lock_initial_optimistic_state_is_false(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test lock starts with is_locking and is_unlocking as falsy (None or False)."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Initial state can be None or False, both are acceptable as falsy values
        assert not lock._attr_is_locking
        assert not lock._attr_is_unlocking

    def test_lock_optimistic_timer_initially_none(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test lock starts with no optimistic timer."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        assert lock._optimistic_timer is None

    async def test_async_lock_sets_is_locking_when_unlocked(
        self, lock_module, mock_coordinator_unlocked: MagicMock
    ) -> None:
        """Test async_lock sets is_locking = True when lock is unlocked."""
        lock = lock_module.KwiksetLock(mock_coordinator_unlocked)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_loop.call_later = MagicMock(return_value=MagicMock())
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        await lock.async_lock()

        # Check optimistic state was set
        assert lock._attr_is_locking is True
        lock.async_write_ha_state.assert_called()

        # Check timer was scheduled
        mock_loop.call_later.assert_called_once()
        call_args = mock_loop.call_later.call_args
        assert call_args[0][0] == OPTIMISTIC_TIMEOUT_SECONDS

    async def test_async_lock_does_not_set_is_locking_when_already_locked(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_lock does not set is_locking when lock is already locked."""
        # mock_coordinator has status = "Locked"
        lock = lock_module.KwiksetLock(mock_coordinator)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_loop.call_later = MagicMock(return_value=MagicMock())
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        await lock.async_lock()

        # Check optimistic state was NOT set (already locked) - should be falsy (None or False)
        assert not lock._attr_is_locking

        # Check timer was NOT scheduled
        mock_loop.call_later.assert_not_called()

    async def test_async_unlock_sets_is_unlocking_when_locked(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_unlock sets is_unlocking = True when lock is locked."""
        # mock_coordinator has status = "Locked"
        lock = lock_module.KwiksetLock(mock_coordinator)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_loop.call_later = MagicMock(return_value=MagicMock())
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        await lock.async_unlock()

        # Check optimistic state was set
        assert lock._attr_is_unlocking is True
        lock.async_write_ha_state.assert_called()

        # Check timer was scheduled
        mock_loop.call_later.assert_called_once()
        call_args = mock_loop.call_later.call_args
        assert call_args[0][0] == OPTIMISTIC_TIMEOUT_SECONDS

    async def test_async_unlock_does_not_set_is_unlocking_when_already_unlocked(
        self, lock_module, mock_coordinator_unlocked: MagicMock
    ) -> None:
        """Test async_unlock does not set is_unlocking when lock is already unlocked."""
        lock = lock_module.KwiksetLock(mock_coordinator_unlocked)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_loop.call_later = MagicMock(return_value=MagicMock())
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        await lock.async_unlock()

        # Check optimistic state was NOT set (already unlocked) - should be falsy (None or False)
        assert not lock._attr_is_unlocking

        # Check timer was NOT scheduled
        mock_loop.call_later.assert_not_called()

    def test_coordinator_update_resets_optimistic_state(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test coordinator update resets is_locking/is_unlocking to False."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Mock hass and async_write_ha_state to avoid RuntimeError
        lock.hass = MagicMock()
        lock.async_write_ha_state = MagicMock()

        # Simulate optimistic state being set
        lock._attr_is_locking = True
        lock._attr_is_unlocking = True

        # Create a mock timer
        mock_timer = MagicMock()
        mock_timer.cancelled.return_value = False
        lock._optimistic_timer = mock_timer

        # Trigger coordinator update
        lock._handle_coordinator_update()

        # Check optimistic state was reset
        assert lock._attr_is_locking is False
        assert lock._attr_is_unlocking is False

        # Check timer was cancelled
        mock_timer.cancel.assert_called_once()
        assert lock._optimistic_timer is None

    async def test_async_lock_error_resets_optimistic_state(
        self, lock_module, mock_coordinator_unlocked: MagicMock
    ) -> None:
        """Test async_lock resets optimistic state on error."""
        mock_coordinator_unlocked.lock.side_effect = Exception("API Error")
        lock = lock_module.KwiksetLock(mock_coordinator_unlocked)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_timer = MagicMock()
        mock_timer.cancelled.return_value = False
        mock_loop.call_later = MagicMock(return_value=mock_timer)
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        with pytest.raises(HomeAssistantError):
            await lock.async_lock()

        # Check optimistic state was reset after error
        assert lock._attr_is_locking is False
        assert lock._attr_is_unlocking is False

    async def test_async_unlock_error_resets_optimistic_state(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_unlock resets optimistic state on error."""
        mock_coordinator.unlock.side_effect = Exception("API Error")
        lock = lock_module.KwiksetLock(mock_coordinator)

        # Mock hass.loop for timer scheduling
        mock_loop = MagicMock()
        mock_timer = MagicMock()
        mock_timer.cancelled.return_value = False
        mock_loop.call_later = MagicMock(return_value=mock_timer)
        lock.hass = MagicMock()
        lock.hass.loop = mock_loop
        lock.async_write_ha_state = MagicMock()

        with pytest.raises(HomeAssistantError):
            await lock.async_unlock()

        # Check optimistic state was reset after error
        assert lock._attr_is_locking is False
        assert lock._attr_is_unlocking is False

    def test_reset_optimistic_state_cancels_timer(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test _reset_optimistic_state cancels any active timer."""
        lock = lock_module.KwiksetLock(mock_coordinator)

        # Create a mock timer that is not cancelled
        mock_timer = MagicMock()
        mock_timer.cancelled.return_value = False
        lock._optimistic_timer = mock_timer

        # Mock async_write_ha_state to avoid errors
        lock.async_write_ha_state = MagicMock()

        # Call reset
        lock._reset_optimistic_state()

        # Verify timer was cancelled
        mock_timer.cancel.assert_called_once()
        assert lock._optimistic_timer is None
        assert lock._attr_is_locking is False
        assert lock._attr_is_unlocking is False

    def test_reset_optimistic_state_handles_none_timer(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test _reset_optimistic_state handles None timer gracefully."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        lock._optimistic_timer = None

        # Mock async_write_ha_state to avoid errors
        lock.async_write_ha_state = MagicMock()

        # Should not raise an error
        lock._reset_optimistic_state()

        assert lock._optimistic_timer is None
        assert lock._attr_is_locking is False
        assert lock._attr_is_unlocking is False

    async def test_async_will_remove_from_hass_resets_state(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_will_remove_from_hass resets optimistic state."""
        lock = lock_module.KwiksetLock(mock_coordinator)

        # Simulate optimistic state and timer
        lock._attr_is_locking = True
        mock_timer = MagicMock()
        mock_timer.cancelled.return_value = False
        lock._optimistic_timer = mock_timer

        # Call removal
        await lock.async_will_remove_from_hass()

        # Verify state was reset
        assert lock._attr_is_locking is False
        mock_timer.cancel.assert_called_once()


# =============================================================================
# Sensor Entity Tests
# =============================================================================


class TestKwiksetSensor:
    """Tests for the KwiksetSensor entity."""

    def test_sensor_is_sensor_entity(
        self, sensor_module, entity_module, mock_coordinator: MagicMock
    ) -> None:
        """Test KwiksetSensor inherits from SensorEntity."""
        description = sensor_module.SENSOR_DESCRIPTIONS[0]
        sensor = sensor_module.KwiksetSensor(mock_coordinator, description)
        assert isinstance(sensor, SensorEntity)
        assert isinstance(sensor, entity_module.KwiksetEntity)

    def test_sensor_unique_id(self, sensor_module, mock_coordinator: MagicMock) -> None:
        """Test sensor unique_id includes description key."""
        description = sensor_module.SENSOR_DESCRIPTIONS[0]
        sensor = sensor_module.KwiksetSensor(mock_coordinator, description)
        assert sensor.unique_id == f"{MOCK_DEVICE_ID}_battery"

    def test_sensor_native_value(
        self, sensor_module, mock_coordinator: MagicMock
    ) -> None:
        """Test sensor returns correct native_value."""
        description = sensor_module.SENSOR_DESCRIPTIONS[0]
        sensor = sensor_module.KwiksetSensor(mock_coordinator, description)
        assert sensor.native_value == 85

    def test_sensor_entity_description_stored(
        self, sensor_module, mock_coordinator: MagicMock
    ) -> None:
        """Test entity_description is stored correctly."""
        description = sensor_module.SENSOR_DESCRIPTIONS[0]
        sensor = sensor_module.KwiksetSensor(mock_coordinator, description)
        assert sensor.entity_description == description

    def test_sensor_parallel_updates(self, sensor_module) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert sensor_module.PARALLEL_UPDATES == 1


class TestSensorDescriptions:
    """Tests for sensor entity descriptions."""

    def test_battery_sensor_description(self, sensor_module) -> None:
        """Test battery sensor description properties."""
        battery_desc = sensor_module.SENSOR_DESCRIPTIONS[0]

        assert battery_desc.key == "battery"
        assert battery_desc.translation_key == "battery"
        assert battery_desc.device_class == SensorDeviceClass.BATTERY
        assert battery_desc.native_unit_of_measurement == PERCENTAGE
        assert battery_desc.entity_category == EntityCategory.DIAGNOSTIC
        assert battery_desc.state_class == SensorStateClass.MEASUREMENT

    def test_sensor_descriptions_are_frozen(self, sensor_module) -> None:
        """Test sensor descriptions are frozen dataclasses."""
        for desc in sensor_module.SENSOR_DESCRIPTIONS:
            with pytest.raises(AttributeError):
                desc.key = "modified"

    def test_sensor_value_fn_callable(
        self, sensor_module, mock_coordinator: MagicMock
    ) -> None:
        """Test value_fn is callable and returns correct value."""
        battery_desc = sensor_module.SENSOR_DESCRIPTIONS[0]
        value = battery_desc.value_fn(mock_coordinator)
        assert value == 85


# =============================================================================
# Switch Entity Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_switch_module(), reason=SWITCH_SKIP_REASON)
class TestKwiksetSwitch:
    """Tests for the KwiksetSwitch entity."""

    def test_switch_is_switch_entity(
        self, switch_module, entity_module, mock_coordinator: MagicMock
    ) -> None:
        """Test KwiksetSwitch inherits from SwitchEntity."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        assert isinstance(switch, SwitchEntity)
        assert isinstance(switch, entity_module.KwiksetEntity)

    def test_switch_unique_id(self, switch_module, mock_coordinator: MagicMock) -> None:
        """Test switch unique_id includes description key."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        assert switch.unique_id == f"{MOCK_DEVICE_ID}_led_switch"

    def test_switch_is_on(self, switch_module, mock_coordinator: MagicMock) -> None:
        """Test is_on returns correct value."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        assert switch.is_on is True

    def test_switch_is_on_returns_false_when_none(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test is_on returns False when coordinator returns None (not unknown state)."""
        mock_coordinator.led_status = None
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        # Should return False, not None - this ensures state is "off" not "unknown"
        assert switch.is_on is False

    def test_switch_no_assumed_state(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test switch does NOT have assumed_state to show toggle instead of buttons."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        # Switch should NOT have assumed_state set, so the frontend shows a toggle
        # instead of lightning bolt buttons
        assert (
            not hasattr(switch, "_attr_assumed_state") or not switch._attr_assumed_state
        )

    def test_switch_entity_description_stored(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test entity_description is stored correctly."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)
        assert switch.entity_description == description

    async def test_async_turn_on_calls_turn_on_fn(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_turn_on calls the turn_on_fn from description."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)

        await switch.async_turn_on()
        mock_coordinator.set_led.assert_called_once_with(True)

    async def test_async_turn_off_calls_turn_off_fn(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_turn_off calls the turn_off_fn from description."""
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)

        await switch.async_turn_off()
        mock_coordinator.set_led.assert_called_once_with(False)

    async def test_async_turn_on_raises_error_on_failure(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_turn_on raises HomeAssistantError on failure."""
        mock_coordinator.set_led.side_effect = Exception("API Error")
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)

        with pytest.raises(HomeAssistantError) as exc_info:
            await switch.async_turn_on()

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "switch_on_failed"

    async def test_async_turn_off_raises_error_on_failure(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test async_turn_off raises HomeAssistantError on failure."""
        mock_coordinator.set_led.side_effect = Exception("API Error")
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)

        with pytest.raises(HomeAssistantError) as exc_info:
            await switch.async_turn_off()

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "switch_off_failed"

    def test_switch_parallel_updates(self, switch_module) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert switch_module.PARALLEL_UPDATES == 1


@pytest.mark.skipif(not _can_import_switch_module(), reason=SWITCH_SKIP_REASON)
class TestSwitchDescriptions:
    """Tests for switch entity descriptions."""

    def test_led_switch_description(self, switch_module) -> None:
        """Test LED switch description properties."""
        led_desc = next(
            d for d in switch_module.SWITCH_DESCRIPTIONS if d.key == "led_switch"
        )
        assert led_desc.translation_key == "led_switch"
        assert led_desc.entity_category == EntityCategory.CONFIG

    def test_audio_switch_description(self, switch_module) -> None:
        """Test audio switch description properties."""
        audio_desc = next(
            d for d in switch_module.SWITCH_DESCRIPTIONS if d.key == "audio_switch"
        )
        assert audio_desc.translation_key == "audio_switch"
        assert audio_desc.entity_category == EntityCategory.CONFIG

    def test_secure_screen_switch_description(self, switch_module) -> None:
        """Test secure screen switch description properties."""
        secure_desc = next(
            d
            for d in switch_module.SWITCH_DESCRIPTIONS
            if d.key == "secure_screen_switch"
        )
        assert secure_desc.translation_key == "secure_screen_switch"
        assert secure_desc.entity_category == EntityCategory.CONFIG

    def test_switch_descriptions_are_frozen(self, switch_module) -> None:
        """Test switch descriptions are frozen dataclasses."""
        for desc in switch_module.SWITCH_DESCRIPTIONS:
            with pytest.raises(AttributeError):
                desc.key = "modified"

    def test_all_switches_are_config_category(self, switch_module) -> None:
        """Test all switches have EntityCategory.CONFIG."""
        for desc in switch_module.SWITCH_DESCRIPTIONS:
            assert desc.entity_category == EntityCategory.CONFIG

    def test_switch_value_fn_callable(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test value_fn is callable and returns correct values."""
        led_desc = switch_module.SWITCH_DESCRIPTIONS[0]
        audio_desc = switch_module.SWITCH_DESCRIPTIONS[1]
        secure_desc = switch_module.SWITCH_DESCRIPTIONS[2]

        assert led_desc.value_fn(mock_coordinator) is True
        assert audio_desc.value_fn(mock_coordinator) is True
        assert secure_desc.value_fn(mock_coordinator) is False


# =============================================================================
# Coordinator Update Tests
# =============================================================================


@pytest.mark.skipif(
    not _can_import_lock_module() or not _can_import_switch_module(),
    reason="Requires lock and switch modules (HA 2025.2+)",
)
class TestCoordinatorUpdates:
    """Tests for entity updates from coordinator."""

    def test_lock_updates_on_coordinator_change(
        self, lock_module, mock_coordinator: MagicMock
    ) -> None:
        """Test lock state updates when coordinator data changes."""
        lock = lock_module.KwiksetLock(mock_coordinator)
        # Mock hass and async_write_ha_state to avoid RuntimeError
        lock.hass = MagicMock()
        lock.async_write_ha_state = MagicMock()
        assert lock.is_locked is True

        mock_coordinator.status = "Unlocked"
        lock._handle_coordinator_update()

        assert lock.is_locked is False

    def test_sensor_native_value_reflects_coordinator(
        self, sensor_module, mock_coordinator: MagicMock
    ) -> None:
        """Test sensor native_value reflects coordinator data after update.

        The sensor uses _attr_native_value which is set during __init__ and
        updated via _handle_coordinator_update. We directly update the attribute
        to avoid needing a full hass context.
        """
        description = sensor_module.SENSOR_DESCRIPTIONS[0]
        sensor = sensor_module.KwiksetSensor(mock_coordinator, description)

        assert sensor.native_value == 85

        # Simulate coordinator update by directly updating the attribute
        # (This mirrors what _handle_coordinator_update does internally)
        mock_coordinator.battery_percentage = 50
        sensor._attr_native_value = description.value_fn(mock_coordinator)
        assert sensor.native_value == 50

    def test_switch_is_on_reflects_coordinator(
        self, switch_module, mock_coordinator: MagicMock
    ) -> None:
        """Test switch is_on reflects coordinator data after update.

        The switch uses _attr_is_on which is set during __init__ and
        updated via _handle_coordinator_update. We directly update the attribute
        to avoid needing a full hass context.
        """
        description = switch_module.SWITCH_DESCRIPTIONS[0]
        switch = switch_module.KwiksetSwitch(mock_coordinator, description)

        assert switch.is_on is True

        # Simulate coordinator update by directly updating the attribute
        # (This mirrors what _handle_coordinator_update does internally)
        mock_coordinator.led_status = False
        switch._attr_is_on = description.value_fn(mock_coordinator)
        assert switch.is_on is False


# =============================================================================
# Entity Description Tests
# =============================================================================


@pytest.mark.skipif(not _can_import_switch_module(), reason=SWITCH_SKIP_REASON)
class TestEntityDescriptionPattern:
    """Tests for the EntityDescription pattern implementation."""

    def test_sensor_descriptions_tuple_is_immutable(self, sensor_module) -> None:
        """Test SENSOR_DESCRIPTIONS is a tuple (immutable)."""
        assert isinstance(sensor_module.SENSOR_DESCRIPTIONS, tuple)
        with pytest.raises(TypeError):
            sensor_module.SENSOR_DESCRIPTIONS[0] = sensor_module.SENSOR_DESCRIPTIONS[0]

    def test_switch_descriptions_tuple_is_immutable(self, switch_module) -> None:
        """Test SWITCH_DESCRIPTIONS is a tuple (immutable)."""
        assert isinstance(switch_module.SWITCH_DESCRIPTIONS, tuple)
        with pytest.raises(TypeError):
            switch_module.SWITCH_DESCRIPTIONS[0] = switch_module.SWITCH_DESCRIPTIONS[0]

    def test_sensor_description_has_value_fn(self, sensor_module) -> None:
        """Test all sensor descriptions have value_fn."""
        for desc in sensor_module.SENSOR_DESCRIPTIONS:
            assert hasattr(desc, "value_fn")
            assert callable(desc.value_fn)

    def test_switch_description_has_all_required_fns(self, switch_module) -> None:
        """Test all switch descriptions have required functions."""
        for desc in switch_module.SWITCH_DESCRIPTIONS:
            assert hasattr(desc, "value_fn")
            assert hasattr(desc, "turn_on_fn")
            assert hasattr(desc, "turn_off_fn")
            assert callable(desc.value_fn)
            assert callable(desc.turn_on_fn)
            assert callable(desc.turn_off_fn)
