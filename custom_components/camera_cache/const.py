"""Public configuration keys and versioned frontend path."""
DOMAIN = "camera_cache"
VERSION = "0.1.0"
STATIC_PATH = "/camera_cache_static"
CARD_PATH = STATIC_PATH + "/camera-cache-card.js"
CARD_URL = CARD_PATH + "?v=" + VERSION
DEFAULTS = {"enabled": True, "refresh_interval": 3, "stale_after": 6, "timeout": 10}


def settings(entry):
    return DEFAULTS | {k: v for k, v in entry.data.items() if k in DEFAULTS} | dict(entry.options)


def validate_settings(values):
    """Reject invalid relations as well as individual field limits."""
    for key, low, high in (("refresh_interval", 2, 3600), ("stale_after", 2, 7200), ("timeout", 1, 60)):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(key)
    if values["stale_after"] < values["refresh_interval"]:
        raise ValueError("stale_after")
    if not isinstance(values["enabled"], bool):
        raise ValueError("enabled")
