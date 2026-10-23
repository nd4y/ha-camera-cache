"""Serve only public JavaScript; frame bytes use the native camera proxy."""
import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .const import CARD_PATH, CARD_URL, DOMAIN, STATIC_PATH

_LOGGER = logging.getLogger(__name__)


async def async_register_frontend(hass):
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("frontend_registered"):
        return
    await hass.http.async_register_static_paths([
        StaticPathConfig(STATIC_PATH, str(Path(__file__).parent / "www"), cache_headers=False)
    ])
    data["frontend_registered"] = True
    resources = hass.data["lovelace"].resources
    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.info("YAML resources: add the module resource %s manually", CARD_URL)
        return
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True
    existing = [item for item in resources.async_items() if item.get("url", "").split("?")[0] == CARD_PATH]
    if existing:
        for item in existing:
            if item.get("url") != CARD_URL or item.get("type") != "module":
                await resources.async_update_item(item["id"], {"url": CARD_URL, "res_type": "module"})
    else:
        await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
