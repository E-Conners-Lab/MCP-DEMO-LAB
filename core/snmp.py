"""SNMP client for device polling.

Uses pysnmp (optional dependency).  If pysnmp is not installed, all
functions raise ``ImportError`` with a user-facing install message.

Install SNMP support with: ``pip install network-mcp[snmp]``
"""

import logging
import os

from config.devices import DEVICES

logger = logging.getLogger(__name__)

SNMP_COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")
SNMP_VERSION = os.getenv("SNMP_VERSION", "2c")
SNMP_PORT = int(os.getenv("SNMP_PORT", "161"))

_INSTALL_MSG = "SNMP support requires pysnmp. Install with: pip install network-mcp[snmp]"


def _check_pysnmp():
    """Raise ImportError with install instructions if pysnmp is missing."""
    try:
        import pysnmp  # noqa: F401
    except ImportError:
        raise ImportError(_INSTALL_MSG)


def _get_host(device_name: str) -> str:
    """Resolve device name to IP address."""
    device = DEVICES.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")
    return device.get("host", "")


async def snmp_get(device_name: str, oid: str) -> dict:
    """SNMP GET for a single OID.

    Returns dict with device, oid, value, type.
    """
    _check_pysnmp()
    from pysnmp.hlapi.v3arch.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        get_cmd,
    )

    host = _get_host(device_name)

    engine = SnmpEngine()
    error_indication, error_status, error_index, var_binds = await get_cmd(
        engine,
        CommunityData(SNMP_COMMUNITY),
        await UdpTransportTarget.create((host, SNMP_PORT)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    if error_indication:
        return {"device": device_name, "oid": oid, "error": str(error_indication)}
    if error_status:
        return {"device": device_name, "oid": oid, "error": str(error_status)}

    for name, val in var_binds:
        return {
            "device": device_name,
            "oid": str(name),
            "value": str(val),
            "type": val.__class__.__name__,
        }

    return {"device": device_name, "oid": oid, "error": "No data returned"}


async def snmp_walk(device_name: str, oid: str) -> dict:
    """SNMP WALK an OID subtree.

    Returns dict with device, base_oid, results list, count.
    """
    _check_pysnmp()
    from pysnmp.hlapi.v3arch.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        bulk_cmd,
    )

    host = _get_host(device_name)
    results = []

    engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, SNMP_PORT))

    kwargs = dict(
        engine,
        CommunityData(SNMP_COMMUNITY),
        transport,
        ContextData(),
        0, 25,  # non-repeaters, max-repetitions
        ObjectType(ObjectIdentity(oid)),
    )

    while True:
        error_indication, error_status, error_index, var_binds = await bulk_cmd(*kwargs)

        if error_indication or error_status:
            break

        for row in var_binds:
            for name, val in row:
                oid_str = str(name)
                if not oid_str.startswith(oid):
                    return {
                        "device": device_name,
                        "base_oid": oid,
                        "results": results,
                        "count": len(results),
                    }
                results.append({
                    "oid": oid_str,
                    "value": str(val),
                    "type": val.__class__.__name__,
                })

        # Update for next iteration
        kwargs = dict(
            engine,
            CommunityData(SNMP_COMMUNITY),
            transport,
            ContextData(),
            0, 25,
            var_binds[-1][-1] if var_binds else ObjectType(ObjectIdentity(oid)),
        )

    return {
        "device": device_name,
        "base_oid": oid,
        "results": results,
        "count": len(results),
    }


async def snmp_poll_device(device_name: str) -> dict:
    """Poll common metrics via SNMP (CPU, memory, interface counters).

    Returns dict with device, cpu, memory, and interface stats.
    """
    _check_pysnmp()

    # Standard OIDs
    cpu_oid = "1.3.6.1.4.1.9.9.109.1.1.1.1.8.1"  # Cisco CPU 5min
    mem_used_oid = "1.3.6.1.4.1.9.9.48.1.1.1.5.1"  # Cisco mem used
    mem_free_oid = "1.3.6.1.4.1.9.9.48.1.1.1.6.1"  # Cisco mem free
    cpu_result = await snmp_get(device_name, cpu_oid)
    mem_used_result = await snmp_get(device_name, mem_used_oid)
    mem_free_result = await snmp_get(device_name, mem_free_oid)

    cpu_pct = None
    mem_pct = None

    if "value" in cpu_result:
        try:
            cpu_pct = int(cpu_result["value"])
        except (ValueError, TypeError):
            pass

    if "value" in mem_used_result and "value" in mem_free_result:
        try:
            used = int(mem_used_result["value"])
            free = int(mem_free_result["value"])
            total = used + free
            if total > 0:
                mem_pct = round(used / total * 100, 1)
        except (ValueError, TypeError):
            pass

    return {
        "device": device_name,
        "cpu_usage_percent": cpu_pct,
        "memory_used_percent": mem_pct,
    }
