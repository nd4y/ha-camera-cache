"""Native authenticated camera whose image method never fetches upstream."""
import asyncio
from contextlib import suppress

from homeassistant.components.camera import Camera, async_get_image
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN, settings, validate_settings
from .frame_cache import FrameCache, image_type
from .source import resolve_source


async def async_setup_entry(hass, entry, async_add_entities):
    options = settings(entry)
    validate_settings(options)
    async_add_entities([CachedCamera(hass, entry, options)])


class CachedCamera(Camera):
    _attr_should_poll = False
    _attr_icon = "mdi:camera-timer"

    def __init__(self, hass, entry, options):
        super().__init__()
        self.hass, self.entry, self.options = hass, entry, options
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            entry_type=DeviceEntryType.SERVICE, manufacturer="Camera Cache",
            model="In-memory snapshot cache",
        )
        self._task = None
        self.cache = FrameCache(self.fetch, interval=options["refresh_interval"],
                                stale_after=options["stale_after"], timeout=options["timeout"],
                                notify=self.async_write_ha_state)

    async def fetch(self):
        source = resolve_source(self.hass, self.entry.data)
        state = self.hass.states.get(source) if source else None
        if state is None or state.state in ("unknown", "unavailable"):
            raise HomeAssistantError("Source unavailable")
        image = await async_get_image(self.hass, source, timeout=self.options["timeout"])
        if image.content_type.split(";")[0].lower() != image_type(image.content):
            raise HomeAssistantError("Unsupported image format")
        return image.content

    @property
    def content_type(self):
        return image_type(self.cache.read()) or "image/jpeg"

    @property
    def available(self):
        return self.options["enabled"]

    async def async_camera_image(self, width=None, height=None):
        return self.cache.read()

    @property
    def extra_state_attributes(self):
        return {"frame_status": self.cache.status if self.options["enabled"] else "disabled",
                "frame_updated_at": self.cache.updated_at,
                "frame_stale_after": self.cache.stale_after,
                "frame_refresh_interval": self.cache.interval,
                "frame_fetch_seconds": self.cache.fetch_seconds,
                "frame_failures": self.cache.failures,
                "frame_error": self.cache.last_error,
                "frame_bytes": len(self.cache.image) if self.cache.image else 0,
                "frame_source": resolve_source(self.hass, self.entry.data), "memory_only": True}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.options["enabled"]:
            self._task = self.entry.async_create_background_task(self.hass, self.cache.run(), "camera cache refresh")

    async def async_will_remove_from_hass(self):
        self.cache.close()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        await super().async_will_remove_from_hass()
