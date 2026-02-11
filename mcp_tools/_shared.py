"""
Shared utilities for MCP tools.

Provides:
- Connection throttling via semaphore
- Demo mode detection
- Common helpers

Demo Mode Design
================
``DEMO_MODE`` is configured via the ``DEMO_MODE=true`` environment variable
(default: false).

**Guarantee**: All tools MUST check demo mode first and NEVER contact real
devices when enabled.

**Pattern**: Every tool function starts with::

    if is_demo_mode():
        return json.dumps({...realistic mock data...}, indent=2)

Tests enforce this by patching Scrapli/Netmiko constructors and asserting
they are never called when ``DEMO_MODE=true``.

**Mock data** lives in this module (``DEMO_DEVICES``, ``DEMO_HEALTH``) and
is structured identically to real responses so AI clients see consistent
behaviour with or without real devices.
"""

import asyncio
import os

# =============================================================================
# Demo Mode
# =============================================================================

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def is_demo_mode() -> bool:
    """Check if running in demo mode (mock data, no real devices)."""
    return DEMO_MODE


# =============================================================================
# Concurrency Control
# =============================================================================

MAX_CONCURRENT_CONNECTIONS = int(os.getenv("MAX_CONCURRENT_CONNECTIONS", "100"))
_connection_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    """Get or create the connection semaphore."""
    global _connection_semaphore
    if _connection_semaphore is None:
        _connection_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONNECTIONS)
    return _connection_semaphore


async def throttled(coro):
    """Execute a coroutine with semaphore-based throttling."""
    sem = get_semaphore()
    async with sem:
        return await coro


# =============================================================================
# Demo Data
# =============================================================================

DEMO_DEVICES = {
    "R1": {
        "device_type": "cisco_xe",
        "host": "10.255.255.11",
        "platform": "C8000V",
        "os_version": "17.13.1a",
    },
    "R2": {
        "device_type": "cisco_xe",
        "host": "10.255.255.12",
        "platform": "C8000V",
        "os_version": "17.13.1a",
    },
    "R3": {
        "device_type": "cisco_xe",
        "host": "10.255.255.13",
        "platform": "C8000V",
        "os_version": "17.13.1a",
    },
    "Switch-R1": {
        "device_type": "cisco_xe",
        "host": "10.255.255.21",
        "platform": "Cat9kv",
        "os_version": "17.13.1a",
    },
    "edge1": {
        "device_type": "containerlab_frr",
        "host": "172.20.20.5",
        "platform": "FRRouting",
        "os_version": "8.4.1",
    },
    "spine1": {
        "device_type": "containerlab_srlinux",
        "host": "172.20.20.10",
        "platform": "SR Linux",
        "os_version": "24.10.1",
    },
}


DEMO_HEALTH = {
    "R1": {
        "device": "R1",
        "status": "healthy",
        "reachable": True,
        "cpu_usage": "3%",
        "memory_usage": "42%",
        "uptime": "14 days, 6 hours",
        "interfaces": {"total": 6, "up": 5, "down": 1},
    },
    "R2": {
        "device": "R2",
        "status": "healthy",
        "reachable": True,
        "cpu_usage": "5%",
        "memory_usage": "38%",
        "uptime": "14 days, 6 hours",
        "interfaces": {"total": 5, "up": 5, "down": 0},
    },
    "R3": {
        "device": "R3",
        "status": "healthy",
        "reachable": True,
        "cpu_usage": "2%",
        "memory_usage": "35%",
        "uptime": "14 days, 6 hours",
        "interfaces": {"total": 6, "up": 4, "down": 2},
    },
    "Switch-R1": {
        "device": "Switch-R1",
        "status": "warning",
        "reachable": True,
        "cpu_usage": "12%",
        "memory_usage": "61%",
        "uptime": "7 days, 3 hours",
        "interfaces": {"total": 12, "up": 10, "down": 2},
    },
    "edge1": {
        "device": "edge1",
        "status": "healthy",
        "reachable": True,
        "cpu_usage": "1%",
        "memory_usage": "22%",
        "uptime": "3 days, 12 hours",
        "interfaces": {"total": 3, "up": 3, "down": 0},
    },
    "spine1": {
        "device": "spine1",
        "status": "healthy",
        "reachable": True,
        "cpu_usage": "4%",
        "memory_usage": "31%",
        "uptime": "3 days, 12 hours",
        "interfaces": {"total": 5, "up": 5, "down": 0},
    },
}
