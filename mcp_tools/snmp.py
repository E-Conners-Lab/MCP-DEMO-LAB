"""
SNMP MCP tools.

- snmp_get_oid: SNMP GET for specific OIDs
- snmp_walk_oid: SNMP WALK subtrees
- snmp_poll_metrics: Poll interface/CPU/memory metrics

Delegates to ``core.snmp`` which requires the ``pysnmp`` optional
dependency.  If not installed, the real implementation returns a
clear user-facing error with install instructions.
"""

import json
import logging

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode

logger = logging.getLogger(__name__)

_INSTALL_MSG = "SNMP support requires pysnmp. Install with: pip install network-mcp[snmp]"


async def snmp_get_oid(device_name: str, oid: str) -> str:
    """
    Perform an SNMP GET on a specific OID.

    Args:
        device_name: Device name from inventory
        oid: OID to query (e.g., "1.3.6.1.2.1.1.1.0" for sysDescr)

    Returns:
        JSON with OID value and type
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "oid": oid,
            "value": "Cisco IOS Software [Dublin], C8000V Software, Version 17.13.1a",
            "type": "OctetString",
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.snmp import snmp_get

        result = await snmp_get(device_name, oid)
        return json.dumps(result, indent=2)

    except ImportError:
        return json.dumps({"error": _INSTALL_MSG})
    except Exception as exc:
        log_event(action="snmp_get_oid", details=str(exc), status="error")
        return json.dumps({"error": f"SNMP GET failed for {device_name}: {exc}"})


async def snmp_walk_oid(device_name: str, oid: str) -> str:
    """
    Perform an SNMP WALK on an OID subtree.

    Args:
        device_name: Device name from inventory
        oid: Base OID to walk (e.g., "1.3.6.1.2.1.2.2.1" for ifTable)

    Returns:
        JSON with all OID-value pairs in the subtree
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "base_oid": oid,
            "results": [
                {"oid": f"{oid}.1.1", "value": "1", "type": "Integer"},
                {"oid": f"{oid}.1.2", "value": "2", "type": "Integer"},
            ],
            "count": 2,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.snmp import snmp_walk

        result = await snmp_walk(device_name, oid)
        return json.dumps(result, indent=2)

    except ImportError:
        return json.dumps({"error": _INSTALL_MSG})
    except Exception as exc:
        log_event(action="snmp_walk_oid", details=str(exc), status="error")
        return json.dumps({"error": f"SNMP WALK failed for {device_name}: {exc}"})


async def snmp_poll_metrics(device_name: str) -> str:
    """
    Poll key metrics via SNMP (CPU, memory, interface counters).

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with CPU usage, memory usage, and interface statistics
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "cpu_usage_percent": 3,
            "memory_used_percent": 42,
            "interfaces": [
                {
                    "name": "GigabitEthernet1", "in_octets": 1234567,
                    "out_octets": 987654, "in_errors": 0, "out_errors": 0,
                },
                {
                    "name": "GigabitEthernet2", "in_octets": 5678901,
                    "out_octets": 4321098, "in_errors": 0, "out_errors": 0,
                },
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.snmp import snmp_poll_device

        result = await snmp_poll_device(device_name)
        return json.dumps(result, indent=2)

    except ImportError:
        return json.dumps({"error": _INSTALL_MSG})
    except Exception as exc:
        log_event(action="snmp_poll_metrics", details=str(exc), status="error")
        return json.dumps({"error": f"SNMP poll failed for {device_name}: {exc}"})


TOOLS = [
    {"fn": snmp_get_oid, "name": "snmp_get_oid", "category": "snmp"},
    {"fn": snmp_walk_oid, "name": "snmp_walk_oid", "category": "snmp"},
    {"fn": snmp_poll_metrics, "name": "snmp_poll_metrics", "category": "snmp"},
]
