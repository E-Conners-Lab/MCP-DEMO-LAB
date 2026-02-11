"""In-memory device data cache with per-entry TTL.

Simple dict-based cache suitable for a single-process MCP server.

Semantics:
- **TTL**: Per-entry, configurable via ``CACHE_TTL`` env var (default 60s).
  No background reaper — entries are checked lazily on access.
- **Eviction**: Stale entries are removed on next access. No max-size cap
  (device count is bounded by the inventory).
- **Concurrency**: The MCP server is single-process. An ``asyncio.Lock``
  guards dict mutations for safety within the event loop.
- **Persistence**: None — cache is lost on process restart (intentional).

Deployment note: Behavior is per-process and non-persistent. Typical
deployment is a single MCP server instance with no cross-process state
sharing.
"""

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

_cache: dict[str, dict] = {}
_lock = asyncio.Lock()


async def get(key: str) -> any:
    """Get a value from the cache, or None if missing/expired."""
    async with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry["expires_at"]:
            del _cache[key]
            logger.debug("Cache miss (expired): %s", key)
            return None
        logger.debug("Cache hit: %s", key)
        return entry["value"]


async def set(key: str, value: any, ttl: int | None = None) -> None:
    """Store a value in the cache with optional custom TTL."""
    effective_ttl = ttl if ttl is not None else CACHE_TTL
    async with _lock:
        _cache[key] = {
            "value": value,
            "expires_at": time.monotonic() + effective_ttl,
        }
    logger.debug("Cache set: %s (ttl=%ds)", key, effective_ttl)


async def delete(key: str) -> bool:
    """Remove a key from the cache. Returns True if it existed."""
    async with _lock:
        return _cache.pop(key, None) is not None


async def clear() -> int:
    """Clear all cache entries. Returns count of entries removed."""
    async with _lock:
        count = len(_cache)
        _cache.clear()
        return count


async def stats() -> dict:
    """Return cache statistics."""
    async with _lock:
        now = time.monotonic()
        total = len(_cache)
        expired = sum(1 for e in _cache.values() if now > e["expires_at"])
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "ttl_seconds": CACHE_TTL,
        }
