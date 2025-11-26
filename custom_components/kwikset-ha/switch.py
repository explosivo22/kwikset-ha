"""Support for Kwikset smart lock switches.

This module provides switch entities for Kwikset smart lock settings.
Currently supports:
    - LED indicator switch (on/off)
    - Audio feedback switch (on/off)
    - Secure screen switch (on/off)

Architecture:
    - Uses translation_key for entity naming (Platinum tier compliance)
    - All switches are EntityCategory.CONFIG as they control device settings
    - All actions delegate to the coordinator (never call API directly)
    - Dynamic device discovery via bus events (Gold tier compliance)
    - PARALLEL_UPDATES = 1 prevents overwhelming the Kwikset cloud
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Limit concurrent API calls to prevent rate limiting
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class KwiksetSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Kwikset switch entity."""

    value_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], bool | None]
    set_fn: Callable[[KwiksetDeviceDataUpdateCoordinator, bool], Awaitable[None]]


SWITCH_DESCRIPTIONS: tuple[KwiksetSwitchEntityDescription, ...] = (
    KwiksetSwitchEntityDescription(
        key="led_switch",
        translation_key="led_switch",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.led_status,
        set_fn=lambda c, v: c.set_led(v),
    ),
    KwiksetSwitchEntityDescription(
        key="audio_switch",
        translation_key="audio_switch",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.audio_status,
        set_fn=lambda c, v: c.set_audio(v),
    ),
    KwiksetSwitchEntityDescription(
        key="secure_screen_switch",
        translation_key="secure_screen_switch",
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
    """Set up Kwikset switch entities from a config entry."""
    devices = entry.runtime_data.devices
    known_ids: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add switch entities for newly discovered devices."""
        new_ids = set(devices.keys()) - known_ids
        if not new_ids:
            return

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
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_new_device", lambda _: _async_add_new_devices())
    )


class KwiksetSwitch(KwiksetEntity, SwitchEntity):
    """Kwikset switch entity for device settings.

    Uses entity descriptions for a data-driven approach.
    All switches use EntityCategory.CONFIG as they control device settings.
    """

    entity_description: KwiksetSwitchEntityDescription

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        description: KwiksetSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(description.key, coordinator)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.coordinator, False)