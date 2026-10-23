import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cache_settings', ROOT/'custom_components/camera_cache/const.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SettingsTests(unittest.TestCase):
    def test_defaults_and_valid_boundaries(self):
        module.validate_settings(module.DEFAULTS)
        for interval, stale, timeout in [(2,2,1),(3600,7200,60),(3,6,10)]:
            module.validate_settings(dict(enabled=True,refresh_interval=interval,stale_after=stale,timeout=timeout))

    def test_invalid_fields_and_relations(self):
        for key, values in {'enabled':[1,None,'true'], 'refresh_interval':[0,1,3601,True,'3',float('nan')], 'stale_after':[0,2,7201], 'timeout':[0,61,True,float('inf')]}.items():
            for value in values:
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    module.validate_settings(module.DEFAULTS | {key:value})

    def test_runtime_has_no_private_installation_or_provider_dependencies(self):
        component=ROOT/'custom_components/camera_cache'
        manifest=json.loads((component/'manifest.json').read_text())
        self.assertEqual(manifest['domain'],'camera_cache')
        self.assertEqual(manifest['dependencies'],['camera','http','lovelace'])
        self.assertEqual(manifest['requirements'],[])
        self.assertEqual(manifest['version'],module.VERSION)
        for file in component.rglob('*'):
            if file.suffix not in ('.py','.js','.json'):continue
            text=file.read_text(encoding='utf-8')
            self.assertNotRegex(text,r'\b(?:\d{1,3}\.){3}\d{1,3}\b',str(file))
            self.assertNotRegex(text,r'(?i)(?:access_token|refresh_token|password)\s*[:=]\s*[\'"][^\'"]{8,}',str(file))
            self.assertNotIn('intercom_audio',text)
            self.assertNotIn('elektronny_gorod',text)

    def test_translations_and_hacs_release_shape(self):
        en=json.loads((ROOT/'custom_components/camera_cache/strings.json').read_text())
        ru=json.loads((ROOT/'custom_components/camera_cache/translations/ru.json').read_text(encoding='utf-8'))
        def shape(value):return {k:shape(v) for k,v in value.items()} if isinstance(value,dict) else None
        self.assertEqual(shape(en),shape(ru))
        hacs=json.loads((ROOT/'hacs.json').read_text())
        self.assertTrue(hacs['zip_release']);self.assertEqual(hacs['filename'],'camera_cache.zip')
        self.assertEqual(len(list((ROOT/'custom_components').iterdir())),1)
