"""Resolve camera references through the native entity registry after renames."""
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def resolve_source(hass, data):
    registry_id = data.get("source_registry_id")
    item = er.async_get(hass).async_get(registry_id) if registry_id else None
    # If a registered entity was deleted, never bind to a new occupant of its ID.
    return item.entity_id if item else (None if registry_id else data.get("source_camera"))


def source_data(hass, entity_id):
    if not isinstance(entity_id, str) or not entity_id.startswith("camera."):
        raise ValueError("invalid_camera")
    item = er.async_get(hass).async_get(entity_id)
    if item and item.platform == DOMAIN:
        raise ValueError("recursive_camera")
    if item is None and hass.states.get(entity_id) is None:
        raise ValueError("invalid_camera")
    data = {"source_camera": entity_id}
    if item:
        data["source_registry_id"] = item.id
    return data


def source_key(data):
    return data.get("source_registry_id", data["source_camera"])
