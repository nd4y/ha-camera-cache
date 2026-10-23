"""Native UI setup and options. No URLs, credentials or provider coupling."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN, settings, validate_settings
from .source import source_data, source_key


def timing_fields(values):
    return {
        vol.Required("refresh_interval", default=values["refresh_interval"]): vol.All(vol.Coerce(float), vol.Range(min=2, max=3600)),
        vol.Required("stale_after", default=values["stale_after"]): vol.All(vol.Coerce(float), vol.Range(min=2, max=7200)),
        vol.Required("timeout", default=values["timeout"]): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
    }


class CameraCacheFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CacheOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                data = source_data(self.hass, user_input["source_camera"])
                values = DEFAULTS | user_input
                validate_settings(values)
            except ValueError as error:
                errors["base"] = str(error) if str(error) in ("invalid_camera", "recursive_camera") else "invalid_timing"
            else:
                await self.async_set_unique_id(source_key(data))
                self._abort_if_unique_id_configured()
                source = self.hass.states.get(data["source_camera"])
                title = user_input.get("name", "").strip() or ((source.name if source else data["source_camera"]) + " cache")
                return self.async_create_entry(title=title, data=data | {k: values[k] for k in DEFAULTS})
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("source_camera"): selector.EntitySelector(selector.EntitySelectorConfig(domain="camera")),
            vol.Optional("name"): str,
            **timing_fields(DEFAULTS),
        }))


class CacheOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                validate_settings(DEFAULTS | user_input)
            except ValueError:
                errors["base"] = "invalid_timing"
            else:
                return self.async_create_entry(title="", data=user_input)
        values = settings(self.config_entry)
        return self.async_show_form(step_id="init", errors=errors, data_schema=vol.Schema({
            vol.Required("enabled", default=values["enabled"]): bool, **timing_fields(values),
        }))
