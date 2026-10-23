"""Deterministic cache lifecycle/failure tests; no HA, images on disk or network."""
import asyncio
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('pure_frame_cache',Path(__file__).parents[1]/'custom_components/camera_cache/frame_cache.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
FrameCache=module.FrameCache
JPEG=b'\xff\xd8demo\xff\xd9'

class CacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now=100.;self.calls=0;self.notifications=0
        async def fetch():self.calls+=1;return JPEG
        self.cache=FrameCache(fetch,clock=lambda:self.now,notify=lambda:setattr(self,'notifications',self.notifications+1),wall_clock=lambda:datetime(2026,1,1,tzinfo=timezone.utc))

    async def test_cold_read_has_no_io(self):
        self.assertIsNone(self.cache.read());self.assertEqual(self.calls,0)
        self.assertEqual(self.cache.status,'waiting')

    async def test_warm_reads_never_fetch_or_copy(self):
        self.assertTrue(await self.cache.refresh())
        for _ in range(1000):self.assertIs(self.cache.read(),JPEG)
        self.assertEqual(self.calls,1);self.assertEqual(self.notifications,1)
        self.assertEqual(self.cache.status,'fresh');self.assertEqual(self.cache.revision,1)

    async def test_fresh_and_stale_boundary(self):
        await self.cache.refresh()
        for age,stale in [(0,False),(3,False),(5.999,False),(6,True),(60,True)]:
            self.now=100+age;self.assertEqual(self.cache.stale,stale)
        self.assertIs(self.cache.read(),JPEG)

    async def test_unreachable_keeps_last_frame_and_safe_error(self):
        await self.cache.refresh();stamp=self.cache.updated_at
        async def fail():raise RuntimeError('secret URL must not be exposed')
        self.cache.fetch=fail;self.assertFalse(await self.cache.refresh())
        self.assertIs(self.cache.read(),JPEG);self.assertEqual(self.cache.updated_at,stamp)
        self.assertEqual(self.cache.last_error,'fetch_failed');self.assertEqual(self.cache.status,'stale')

    async def test_error_before_first_frame(self):
        async def fail():raise RuntimeError()
        self.cache.fetch=fail;await self.cache.refresh()
        self.assertIsNone(self.cache.read());self.assertEqual(self.cache.status,'unavailable')

    async def test_recovery_replaces_single_buffer(self):
        await self.cache.refresh()
        async def fail():raise RuntimeError()
        self.cache.fetch=fail;await self.cache.refresh()
        other=b'\xff\xd8new frame\xff\xd9'
        async def recover():return other
        self.now+=3;self.cache.fetch=recover;await self.cache.refresh()
        self.assertIs(self.cache.read(),other);self.assertEqual(self.cache.status,'fresh')
        self.assertEqual(self.cache.failures,0);self.assertIsNone(self.cache.last_error)

    async def test_invalid_and_oversized_data_cannot_replace_frame(self):
        await self.cache.refresh()
        for image in [None,b'',b'not jpeg',bytearray(JPEG),b'\xff\xd8'+b'x'*module.MAX_IMAGE_BYTES+b'\xff\xd9',b'\xff\xd8truncated']:
            async def fetch(image=image):return image
            self.cache.fetch=fetch;self.assertFalse(await self.cache.refresh());self.assertIs(self.cache.read(),JPEG)

    async def test_timeout_retains_last_frame(self):
        await self.cache.refresh()
        async def hang():await asyncio.Event().wait()
        self.cache.fetch=hang;self.cache.timeout=.001
        await self.cache.refresh();self.assertEqual(self.cache.last_error,'timeout');self.assertIs(self.cache.read(),JPEG)

    async def test_no_overlapping_upstream_requests(self):
        gate=asyncio.Event()
        async def fetch():self.calls+=1;await gate.wait();return JPEG
        self.cache.fetch=fetch;first=asyncio.create_task(self.cache.refresh());await asyncio.sleep(0)
        self.assertFalse(await self.cache.refresh());self.assertEqual(self.calls,1)
        gate.set();self.assertTrue(await first)

    async def test_closed_inflight_cannot_restore_bytes(self):
        gate=asyncio.Event()
        async def fetch():await gate.wait();return JPEG
        self.cache.fetch=fetch;task=asyncio.create_task(self.cache.refresh());await asyncio.sleep(0)
        self.cache.close();gate.set();self.assertFalse(await task)
        self.assertIsNone(self.cache.read());self.assertEqual(self.notifications,0)

    async def test_close_discards_frame_and_stops_new_fetches(self):
        await self.cache.refresh();self.cache.close()
        self.assertIsNone(self.cache.read());self.assertIsNone(self.cache.updated_at)
        self.assertFalse(await self.cache.refresh());self.assertEqual(self.calls,1)

    async def test_cancellation_is_not_reported_as_source_failure(self):
        async def hang():await asyncio.Event().wait()
        self.cache.fetch=hang;task=asyncio.create_task(self.cache.refresh());await asyncio.sleep(0);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.cache.failures,0)

    async def test_start_to_start_interval_and_backoff(self):
        self.assertEqual(self.cache.delay(1.9),1.1);self.assertEqual(self.cache.delay(4),0)
        self.cache.failures=1;self.assertEqual(self.cache.delay(0),6)
        self.cache.failures=99;self.assertEqual(self.cache.delay(0),30)
        self.cache.interval=60;self.assertEqual(self.cache.delay(0),60)

    async def test_worker_repeats_and_cancels(self):
        self.cache.interval=.002
        task=asyncio.create_task(self.cache.run())
        for _ in range(50):
            if self.calls>=2:break
            await asyncio.sleep(.001)
        self.cache.close();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertGreaterEqual(self.calls,2);self.assertIsNone(self.cache.read())

    async def test_timing_validation(self):
        for invalid in [0,-1,True,'3',float('nan'),float('inf')]:
            with self.assertRaises(ValueError):FrameCache(self.cache.fetch,interval=invalid)
        with self.assertRaises(ValueError):FrameCache(self.cache.fetch,interval=3,stale_after=2)

