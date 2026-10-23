"""One bounded image in RAM; readers never wait for upstream IO."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Awaitable, Callable

MAX_IMAGE_BYTES = 2 * 1024 * 1024


def image_type(image):
    """Accept bounded raster snapshots only; never HTML, SVG or video."""
    if not isinstance(image, bytes) or not 4 <= len(image) <= MAX_IMAGE_BYTES:
        return None
    if image.startswith(b'\xff\xd8') and image.endswith(b'\xff\xd9'):
        return "image/jpeg"
    if image.startswith(b'\x89PNG\r\n\x1a\n') and image.endswith(b'IEND\xaeB`\x82'):
        return "image/png"
    return None


class FrameCache:
    def __init__(self, fetch: Callable[[], Awaitable[bytes]], *, interval=3,
                 stale_after=6, timeout=10, clock=time.monotonic,
                 wall_clock=lambda: datetime.now(timezone.utc), notify=lambda: None):
        for value in (interval, stale_after, timeout):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 7200:
                raise ValueError("Invalid cache timing")
        if stale_after < interval:
            raise ValueError("Stale threshold must cover one interval")
        self.fetch, self.interval, self.stale_after, self.timeout = fetch, interval, stale_after, timeout
        self.clock, self.wall_clock, self.notify = clock, wall_clock, notify
        self.image: bytes | None = None
        self.updated_at: str | None = None
        self.received: float | None = None
        self.last_error: str | None = None
        self.fetch_seconds: float | None = None
        self.failures = self.revision = 0
        self._lock = asyncio.Lock()
        self.closed = False

    @property
    def age(self):
        return None if self.received is None else max(0, self.clock() - self.received)

    @property
    def stale(self):
        return self.image is not None and (self.last_error is not None or self.age >= self.stale_after)

    @property
    def status(self):
        if self.image is None:
            return "unavailable" if self.last_error else "waiting"
        return "stale" if self.stale else "fresh"

    def read(self):
        return self.image

    async def refresh(self):
        if self.closed or self._lock.locked():
            return False
        async with self._lock:
            started = self.clock()
            try:
                async with asyncio.timeout(self.timeout):
                    image = await self.fetch()
                if image_type(image) is None:
                    raise ValueError("Invalid raster frame")
                if self.closed:
                    return False
                self.image = image
                self.received = self.clock()
                self.updated_at = self.wall_clock().isoformat()
                self.fetch_seconds = max(0, self.received - started)
                self.last_error = None
                self.failures = 0
                self.revision += 1
                return True
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Exception messages can contain private source URLs/tokens.
                self.last_error = "timeout" if isinstance(error, TimeoutError) else "fetch_failed"
                self.failures += 1
                return False
            finally:
                if not self.closed:
                    self.notify()

    def delay(self, elapsed):
        # Normal start-to-start polling; bounded backoff when a source fails.
        period = max(self.interval, min(30, self.interval * 2 ** min(self.failures, 4))) if self.failures else self.interval
        return max(0, period - elapsed)

    async def run(self):
        while not self.closed:
            started = self.clock()
            await self.refresh()
            await asyncio.sleep(self.delay(max(0, self.clock() - started)))

    def close(self):
        self.closed = True
        self.image = None
        self.received = None
        self.updated_at = None
