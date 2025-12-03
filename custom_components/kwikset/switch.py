"""Support for Kwikset smart lock switches.

Provides switch entities for Kwikset lock settings (LED, audio, secure screen).
All switches use EntityCategory.CONFIG as they control device settings.

Quality Scale: Bronze (has_entity_name, entity_unique_id),
Silver (parallel_updates, action_exceptions), Gold (dynamic_devices).
"""

from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .const import LOGGER
from .const import PARALLEL_UPDATES as _PARALLEL_UPDATES
from .entity import KwiksetEntity

if TYPE_CHECKING:
    from . import KwiksetConfigEntry
    from .device import KwiksetDeviceDataUpdateCoordinator

# Silver tier: parallel_updates - serialize API calls to prevent rate limiting
PARALLEL_UPDATES: int = _PARALLEL_UPDATES


class KwiksetSwitchEntityDescription(
    SwitchEntityDescription, frozen_or_thawed=True, kw_only=True
):
    """Describes a Kwikset switch entity with value and control functions."""

    value_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], bool | None]
    turn_on_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], Awaitable[None]]
    turn_off_fn: Callable[[KwiksetDeviceDataUpdateCoordinator], Awaitable[None]]


SWITCH_DESCRIPTIONS: tuple[KwiksetSwitchEntityDescription, ...] = (
    KwiksetSwitchEntityDescription(
        key="led_switch",
        translation_key="led_switch",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.led_status,
        turn_on_fn=lambda c: c.set_led(True),
        turn_off_fn=lambda c: c.set_led(False),
    ),
    KwiksetSwitchEntityDescription(
        key="audio_switch",
        translation_key="audio_switch",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda c: c.audio_status,
        turn_on_fn=lambda c: c.set_audio(True),
        turn_off_fn=lambda c: c.set_audio(False),
    ),
    KwiksetSwitchEntityDescription(
        key="secure_screen_switch",
        translation_key="secure_screen_switch",
        icon="mdi:shield-lock",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.secure_screen_status,
        turn_on_fn=lambda c: c.set_secure_screen(True),
        turn_off_fn=lambda c: c.set_secure_screen(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwiksetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kwikset switch entities from a config entry.

    Gold tier: dynamic_devices - supports runtime discovery via bus events.
    Creates LED, audio, and secure screen switches for each device.
    """
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

    _async_add_new_devices()

    entry.async_on_unload(
        hass.bus.async_listen(
            f"{DOMAIN}_new_device", lambda _: _async_add_new_devices()
        )
    )


class KwiksetSwitch(KwiksetEntity, SwitchEntity):
    """Kwikset switch entity for device settings.

    Uses entity descriptions for data-driven entity creation.
    All switches are CONFIG category as they control device settings.

    Note: We override is_on as a property (not _attr_is_on) to ensure
    the value is always fresh and never None, which prevents the
    "unknown" state that causes lightning bolt buttons in the UI.
    """

    entity_description: KwiksetSwitchEntityDescription

    def __init__(
        self,
        coordinator: KwiksetDeviceDataUpdateCoordinator,
        description: KwiksetSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        self.entity_description = description
        super().__init__(description.key, coordinator)

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on.

        Always returns a boolean (never None) to ensure the entity
        state is always "on" or "off", never "unknown". This prevents
        the frontend from showing lightning bolt buttons instead of
        a toggle switch.

        Returns False if the actual state is unknown/None.
        """
        value = self.entity_description.value_fn(self.coordinator)
        return value if value is not None else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_on_failed",
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_off_failed",
            ) from err
