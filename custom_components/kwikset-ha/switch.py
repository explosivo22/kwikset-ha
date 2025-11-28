"""Support for Kwikset smart lock switches.

This module provides switch entities for Kwikset smart lock settings.
Currently supports:
    - LED indicator switch (on/off)
    - Audio feedback switch (on/off)
    - Secure screen switch (on/off)

Architecture:
    - Uses translation_key for entity naming (Bronze: has_entity_name)
    - Uses entity descriptions for data-driven entity creation
    - All switches are EntityCategory.CONFIG as they control device settings
    - All actions delegate to the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold: dynamic_devices)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud

Quality Scale Compliance:
    Bronze tier:
        - has_entity_name: Uses translation_key via entity descriptions
        - entity_unique_id: Inherited from KwiksetEntity base class

    Silver tier:
        - parallel_updates: PARALLEL_UPDATES = 1 limits concurrent API calls
        - action_exceptions: Raises HomeAssistantError with translation_key
        - entity_unavailable: Inherited from KwiksetEntity.available

    Gold tier:
        - dynamic_devices: Listens for "{DOMAIN}_new_device" bus events

Entity Descriptions Pattern:
    This module uses entity descriptions (KwiksetSwitchEntityDescription) for a
    data-driven approach to entity creation. Each description contains:
    - key: Unique identifier for the switch type
    - translation_key: Reference to strings.json for localized name
    - entity_category: CONFIG because these are device settings
    - value_fn: Lambda to read state from coordinator
    - set_fn: Lambda to write state via coordinator

    This pattern reduces code duplication when multiple entities share the
    same behavior with different data sources.

Entity Categories:
    All switches use EntityCategory.CONFIG because:
    - They control device settings (LED, audio, secure screen)
    - They're not primary measurements or controls
    - Users typically configure these once, not frequently
    - HA automatically groups config entities together
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates
# PARALLEL_UPDATES imported from const.py - limits concurrent API calls to 1
# Switch operations (turn on/off) are serialized to prevent API rate limiting


@dataclass(frozen=True, kw_only=True)
class KwiksetSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Kwikset switch entity.

    Extends SwitchEntityDescription with Kwikset-specific fields:
    - value_fn: Lambda to read current state from coordinator
    - set_fn: Lambda to write new state via coordinator

    This data-driven approach allows defining multiple switches
    with similar behavior in a declarative manner.

    Attributes:
        key: Unique identifier for the switch (used in unique_id)
        translation_key: Reference to strings.json for entity name
        entity_category: EntityCategory.CONFIG for all settings
        value_fn: Callable that returns current state (bool | None)
        set_fn: Async callable that sets new state
    """

    value_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], bool | None]
    set_fn: Callable[[KwiksetDeviceDataUpdateCoordinator, bool], Awaitable[None]]


# Switch entity descriptions - defines all available switches
# Each tuple entry creates one switch entity per device
SWITCH_DESCRIPTIONS: tuple[KwiksetSwitchEntityDescription, ...] = (
    KwiksetSwitchEntityDescription(
        key="led_switch",
        translation_key="led_switch",  # Maps to entity.switch.led_switch.name → "LED"
        entity_category=EntityCategory.CONFIG,  # Device setting, not primary control
        value_fn=lambda c: c.led_status,
        set_fn=lambda c, v: c.set_led(v),
    ),
    KwiksetSwitchEntityDescription(
        key="audio_switch",
        translation_key="audio_switch",  # Maps to entity.switch.audio_switch.name → "Audio"
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.audio_status,
        set_fn=lambda c, v: c.set_audio(v),
    ),
    KwiksetSwitchEntityDescription(
        key="secure_screen_switch",
        translation_key="secure_screen_switch",  # Maps to entity.switch.secure_screen_switch.name
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.secure_screen_status,
        set_fn=lambda c, v: c.set_secure_screen(v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset switch entities from a config entry.

    Gold tier: dynamic_devices
    Creates switch entities for each device using entity descriptions.
    Supports runtime discovery of new devices via bus events.

    Entity Creation:
        For each device, creates one switch entity per SWITCH_DESCRIPTIONS entry.
        This means each lock gets: LED switch, Audio switch, Secure Screen switch.

    Args:
        hass: Home Assistant instance
        entry: Config entry being set up
        async_add_entities: Callback to add entities to HA
    """
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add switch entities for newly discovered devices.

        Gold tier: dynamic_devices
        Creates all switch types for each new device.
        Uses generator expression for efficient entity creation.
        """
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

        # Create one entity per device per switch description
        async_add_entities(
            KwiksetSwitch(devices[device_id], description)
            for device_id in new_ids
            for description in SWITCH_DESCRIPTIONS
        )
        known_ids.update(new_ids)
        LOGGER.debug("Added switch entities for devices: %s", new_ids)

    # Add existing devices
    _async_add_new_devices()

    # Listen for new device discovery events
    # Gold tier: dynamic_devices - runtime discovery support
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetSwitch(KwiksetEntity, SwitchEntity):
    """Kwikset switch entity for device settings.

    Uses entity descriptions for a data-driven approach.
    All switches use EntityCategory.CONFIG as they control device settings.

    Quality Scale Implementation:
        Bronze - has_entity_name:
            Uses translation_key from entity description which maps to
            entity.switch.<key>.name in strings.json
        
        Bronze - entity_unique_id:
            Inherited from KwiksetEntity: {device_id}_{description.key}
        
        Silver - action_exceptions:
            async_turn_on/off raise HomeAssistantError with translation_key
        
        Silver - entity_unavailable:
            Inherited from KwiksetEntity.available property

    Entity Description Pattern:
        - is_on reads from description.value_fn(coordinator)
        - turn_on/off calls description.set_fn(coordinator, value)
        This keeps the entity class generic while descriptions define specifics.

    Attributes:
        entity_description: The switch description for this instance
    """

    entity_description: KwiksetSwitchEntityDescription

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        description: KwiksetSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity.

        Args:
            coordinator: Device coordinator for this lock
            description: Entity description defining switch behavior
        """
        # Bronze tier: entity_unique_id via parent class
        # Creates unique_id: {device_id}_{description.key}
        super().__init__(description.key, coordinator)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on.

        Uses description.value_fn to read state from coordinator.
        Returns None if state is unknown.

        Returns:
            True if on, False if off, None if unknown
        """
        return self.entity_description.value_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on.

        Silver tier: action_exceptions
        Uses description.set_fn to call coordinator method.
        Coordinator handles API call, retries, and token refresh.

        Raises:
            HomeAssistantError: If the operation fails.
                Uses translation_key for user-friendly message.
        """
        try:
            await self.entity_description.set_fn(self.coordinator, True)
        except Exception as err:
            # Silver tier: action_exceptions with translation_key
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_on_failed",
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off.

        Silver tier: action_exceptions
        Uses description.set_fn to call coordinator method.
        Coordinator handles API call, retries, and token refresh.

        Raises:
            HomeAssistantError: If the operation fails.
                Uses translation_key for user-friendly message.
        """
        try:
            await self.entity_description.set_fn(self.coordinator, False)
        except Exception as err:
            # Silver tier: action_exceptions with translation_key
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_off_failed",
            ) from err