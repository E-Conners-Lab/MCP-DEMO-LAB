"""
Topology discovery MCP tools.

- discover_topology: LLDP-based network topology discovery
- lldp_neighbors: Get LLDP neighbors for a device
- lldp_check_status: Check LLDP status on a device

Delegates to ``core.lldp`` for all LLDP operations.
"""

import json
import logging

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode

logger = logging.getLogger(__name__)


async def discover_topology() -> str:
    """
    Discover the network topology using LLDP.

    Queries all devices in the inventory for LLDP neighbor information
    and builds a topology map showing device interconnections.

    Returns:
        JSON with nodes (devices) and edges (links) forming the topology
    """
    if is_demo_mode():
        return json.dumps({
            "nodes": ["R1", "R2", "R3", "Switch-R1", "edge1", "spine1"],
            "edges": [
                {
                    "from": "R1", "to": "R2",
                    "local_port": "GigabitEthernet2",
                    "remote_port": "GigabitEthernet2",
                },
                {
                    "from": "R2", "to": "R3",
                    "local_port": "GigabitEthernet3",
                    "remote_port": "GigabitEthernet2",
                },
                {
                    "from": "R1", "to": "Switch-R1",
                    "local_port": "GigabitEthernet4",
                    "remote_port": "GigabitEthernet0/1",
                },
                {"from": "edge1", "to": "spine1", "local_port": "eth1", "remote_port": "e1-1"},
            ],
            "device_count": 6,
            "link_count": 4,
        }, indent=2)

    try:
        from core.lldp import discover_lldp_topology

        result = await discover_lldp_topology()
        return json.dumps(result, indent=2)

    except Exception as exc:
        log_event(action="discover_topology", details=str(exc), status="error")
        return json.dumps({"error": f"Topology discovery failed: {exc}"})


async def lldp_neighbors(device_name: str) -> str:
    """
    Get LLDP neighbors for a specific device.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with LLDP neighbor details (remote device, port, capabilities)
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "neighbors": [
                {
                    "local_port": "GigabitEthernet2",
                    "remote_device": "R2",
                    "remote_port": "GigabitEthernet2",
                    "capabilities": "Router",
                },
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.lldp import discover_lldp_neighbors

        neighbors = await discover_lldp_neighbors(device_name)
        return json.dumps({
            "device": device_name,
            "neighbors": neighbors,
        }, indent=2)

    except Exception as exc:
        log_event(action="lldp_neighbors", details=str(exc), status="error")
        return json.dumps({"error": f"LLDP query failed for {device_name}: {exc}"})


async def lldp_check_status(device_name: str) -> str:
    """
    Check LLDP status on a device.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with LLDP enabled status and timer settings
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "lldp_enabled": True,
            "hold_time": 120,
            "timer": 30,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.lldp import check_lldp_enabled

        result = await check_lldp_enabled(device_name)
        return json.dumps(result, indent=2)

    except Exception as exc:
        log_event(action="lldp_check_status", details=str(exc), status="error")
        return json.dumps({"error": f"LLDP status check failed for {device_name}: {exc}"})


TOOLS = [
    {"fn": discover_topology, "name": "discover_topology", "category": "topology"},
    {"fn": lldp_neighbors, "name": "lldp_neighbors", "category": "topology"},
    {"fn": lldp_check_status, "name": "lldp_check_status", "category": "topology"},
]
