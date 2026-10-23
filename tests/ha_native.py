"""Adapter tests against real HA libraries, with no external network or devices."""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from homeassistant.core import HomeAssistant
from homeassistant.components.camera import Camera
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import area_registry, device_registry, floor_registry, label_registry

from custom_components.camera_cache.camera import CachedCamera
from custom_components.camera_cache.config_flow import CameraCacheFlow, CacheOptionsFlow
from custom_components.camera_cache.const import CARD_URL, DEFAULTS, DOMAIN
from custom_components.camera_cache.frontend import async_register_frontend
from custom_components.camera_cache.source import source_data, resolve_source

JPEG=b'\xff\xd8synthetic\xff\xd9'


class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.hass=HomeAssistant(self.temp.name)
        await floor_registry.async_load(self.hass)
        await area_registry.async_load(self.hass)
        await label_registry.async_load(self.hass)
        self.hass.data[device_registry.DATA_REGISTRY]=device_registry.DeviceRegistry(self.hass)
        await device_registry.async_load(self.hass)
        await er.async_load(self.hass)
        self.registry=er.async_get(self.hass)
        self.source=self.registry.async_get_or_create('camera','test_source','source-1',suggested_object_id='synthetic_source')
        self.hass.states.async_set(self.source.entity_id,'idle',{'friendly_name':'Synthetic camera'})
        self.data=source_data(self.hass,self.source.entity_id)
        self.entry=SimpleNamespace(entry_id='cache-entry',title='Synthetic preview',data=self.data,options={})
        self.camera=CachedCamera(self.hass,self.entry,DEFAULTS)
        self.camera.async_write_ha_state=Mock()
        self.camera.cache.notify=self.camera.async_write_ha_state

    async def asyncTearDown(self):
        self.camera.cache.close()
        await self.hass.async_stop()
        self.temp.cleanup()

    async def test_native_registry_rename_and_delete(self):
        self.registry.async_update_entity(self.source.entity_id,new_entity_id='camera.renamed_synthetic')
        self.assertEqual(resolve_source(self.hass,self.data),'camera.renamed_synthetic')
        self.registry.async_remove('camera.renamed_synthetic')
        self.hass.states.async_set(self.source.entity_id,'idle')
        self.assertIsNone(resolve_source(self.hass,self.data))

    async def test_unregistered_source_and_recursive_rejection(self):
        self.hass.states.async_set('camera.unregistered','idle')
        self.assertEqual(source_data(self.hass,'camera.unregistered'),{'source_camera':'camera.unregistered'})
        item=self.registry.async_get_or_create('camera',DOMAIN,'cache-other')
        for entity in (item.entity_id,'sensor.wrong','camera.missing'):
            with self.assertRaises(ValueError):source_data(self.hass,entity)

    async def test_native_fetch_cached_read_and_error_retention(self):
        with patch('custom_components.camera_cache.camera.async_get_image',AsyncMock(return_value=SimpleNamespace(content_type='image/jpeg',content=JPEG))) as fetch:
            self.assertIsNone(await self.camera.async_camera_image())
            fetch.assert_not_awaited()
            self.assertTrue(await self.camera.cache.refresh())
            for _ in range(10):self.assertIs(await self.camera.async_camera_image(),JPEG)
            fetch.assert_awaited_once()
        self.hass.states.async_set(self.source.entity_id,'unavailable')
        self.assertFalse(await self.camera.cache.refresh())
        self.assertIs(await self.camera.async_camera_image(),JPEG)
        self.assertEqual(self.camera.extra_state_attributes['frame_status'],'stale')
        self.assertTrue(self.camera.extra_state_attributes['memory_only'])

    async def test_png_and_content_type_mismatch(self):
        png=b'\x89PNG\r\n\x1a\nsyntheticIEND\xaeB`\x82'
        with patch('custom_components.camera_cache.camera.async_get_image',AsyncMock(return_value=SimpleNamespace(content_type='image/png',content=png))):
            self.assertTrue(await self.camera.cache.refresh())
            self.assertEqual(self.camera.content_type,'image/png')
        with patch('custom_components.camera_cache.camera.async_get_image',AsyncMock(return_value=SimpleNamespace(content_type='image/jpeg',content=png))):
            self.assertFalse(await self.camera.cache.refresh())
            self.assertIs(self.camera.cache.read(),png)

    async def test_worker_unload_cancels_own_task_and_discards_frame(self):
        self.entry.async_create_background_task=lambda hass,coro,name:asyncio.create_task(coro)
        with patch.object(Camera,'async_added_to_hass',AsyncMock()), patch.object(Camera,'async_will_remove_from_hass',AsyncMock()), patch.object(self.camera,'fetch',AsyncMock(return_value=JPEG)):
            self.camera.cache.fetch=self.camera.fetch
            await self.camera.async_added_to_hass()
            await asyncio.sleep(.01)
            self.assertIs(self.camera.cache.read(),JPEG)
            await self.camera.async_will_remove_from_hass()
            self.assertTrue(self.camera._task.cancelled())
            self.assertIsNone(self.camera.cache.read())

    async def test_disabled_cache_never_starts_worker(self):
        camera=CachedCamera(self.hass,self.entry,DEFAULTS|{'enabled':False})
        self.entry.async_create_background_task=Mock()
        with patch.object(Camera,'async_added_to_hass',AsyncMock()):await camera.async_added_to_hass()
        self.entry.async_create_background_task.assert_not_called()
        self.assertFalse(camera.available)
        self.assertEqual(camera.extra_state_attributes['frame_status'],'disabled')

    async def test_config_flow_validation_and_configurable_source(self):
        flow=CameraCacheFlow();flow.hass=self.hass;flow.context={'source':'user'};flow.flow_id='test-flow';flow.handler=DOMAIN
        flow.async_set_unique_id=AsyncMock();flow._abort_if_unique_id_configured=Mock()
        result=await flow.async_step_user({'source_camera':self.source.entity_id,'name':'Preview',**{k:v for k,v in DEFAULTS.items() if k!='enabled'}})
        self.assertEqual(result['title'],'Preview')
        self.assertEqual(result['data']['source_registry_id'],self.source.id)
        flow.async_set_unique_id.assert_awaited_once_with(self.source.id)
        invalid=await flow.async_step_user({'source_camera':self.source.entity_id,'refresh_interval':10,'stale_after':2,'timeout':10})
        self.assertEqual(invalid['errors'],{'base':'invalid_timing'})
        bad=await flow.async_step_user({'source_camera':'sensor.wrong'})
        self.assertEqual(bad['errors'],{'base':'invalid_camera'})

    async def test_options_reject_bad_timing(self):
        flow=CacheOptionsFlow();flow.hass=self.hass;flow.flow_id='options-flow';flow.handler='cache-entry'
        with patch.object(CacheOptionsFlow,'config_entry',property(lambda _:self.entry)):
            bad=await flow.async_step_init(DEFAULTS|{'stale_after':2})
            self.assertEqual(bad['errors'],{'base':'invalid_timing'})
            good=await flow.async_step_init(DEFAULTS|{'refresh_interval':5,'stale_after':12})
            self.assertEqual(good['data']['refresh_interval'],5)

    async def test_frontend_registration_creation_and_idempotence(self):
        resources=Mock(spec=ResourceStorageCollection);resources.loaded=True;resources.async_items.return_value=[]
        resources.async_create_item=AsyncMock();self.hass.data['lovelace']=SimpleNamespace(resources=resources)
        self.hass.http=SimpleNamespace(async_register_static_paths=AsyncMock())
        await async_register_frontend(self.hass);await async_register_frontend(self.hass)
        self.hass.http.async_register_static_paths.assert_awaited_once()
        resources.async_create_item.assert_awaited_once_with({'url':CARD_URL,'res_type':'module'})

    async def test_frontend_upgrade_updates_only_its_own_resource(self):
        resources=Mock(spec=ResourceStorageCollection);resources.loaded=True
        resources.async_items.return_value=[{'id':'own','url':CARD_URL.split('?')[0]+'?v=old','type':'module'},{'id':'other','url':'/other.js','type':'module'}]
        resources.async_update_item=AsyncMock();self.hass.data['lovelace']=SimpleNamespace(resources=resources)
        self.hass.http=SimpleNamespace(async_register_static_paths=AsyncMock())
        await async_register_frontend(self.hass)
        resources.async_update_item.assert_awaited_once_with('own',{'url':CARD_URL,'res_type':'module'})

    async def test_yaml_resources_are_not_mutated(self):
        self.hass.data['lovelace']=SimpleNamespace(resources=SimpleNamespace())
        self.hass.http=SimpleNamespace(async_register_static_paths=AsyncMock())
        await async_register_frontend(self.hass)
        self.assertTrue(self.hass.data[DOMAIN]['frontend_registered'])


if __name__=='__main__':unittest.main(verbosity=2)
