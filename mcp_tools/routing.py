"""
Routing MCP tools.

- get_routing_table: Get device routing table (IOS-XE route parsing)
- get_neighbors: Get routing protocol neighbor status (OSPF + BGP)

Public API note: ``get_neighbors`` returns routing protocol neighbors
(OSPF, BGP), not L2 discovery (CDP/LLDP).
"""

import json
import logging
import re

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode, throttled

logger = logging.getLogger(__name__)


async def get_routing_table(device_name: str, protocol: str = None) -> str:
    """
    Get the routing table from a device.

    Args:
        device_name: Device name from inventory
        protocol: Filter by protocol ("ospf", "bgp", "static", "connected")

    Returns:
        JSON with routing entries (prefix, next_hop, protocol, metric, interface)

    Example response::

        {
          "device": "R1",
          "routes": [
            {"prefix": "10.0.12.0/30", "next_hop": "connected",
             "protocol": "connected", "interface": "GigabitEthernet2"}
          ],
          "total": 1
        }
    """
    if is_demo_mode():
        routes = [
            {
                "prefix": "10.0.12.0/30", "next_hop": "connected",
                "protocol": "connected", "interface": "GigabitEthernet2",
            },
            {
                "prefix": "10.0.23.0/30", "next_hop": "10.0.12.2",
                "protocol": "ospf", "metric": 2,
                "interface": "GigabitEthernet2",
            },
            {
                "prefix": "198.51.100.2/32", "next_hop": "10.0.12.2",
                "protocol": "ospf", "metric": 2,
                "interface": "GigabitEthernet2",
            },
            {
                "prefix": "198.51.100.3/32", "next_hop": "10.0.12.2",
                "protocol": "ospf", "metric": 3,
                "interface": "GigabitEthernet2",
            },
            {
                "prefix": "0.0.0.0/0", "next_hop": "10.255.255.1",
                "protocol": "static", "interface": "GigabitEthernet1",
            },
        ]
        if protocol:
            routes = [r for r in routes if r["protocol"] == protocol.lower()]
        return json.dumps({"device": device_name, "routes": routes, "total": len(routes)}, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.scrapli_manager import send_command
        from core.unified_parser import parse_show_ip_route

        raw = await throttled(send_command(device_name, "show ip route"))
        parsed = parse_show_ip_route(raw)

        routes = []
        for entry in parsed:
            route = {
                "prefix": entry.get("prefix", ""),
                "next_hop": entry.get("next_hop", ""),
                "protocol": entry.get("protocol", ""),
                "interface": entry.get("interface", ""),
            }
            if "metric" in entry:
                route["metric"] = entry["metric"]
            if "distance" in entry:
                route["distance"] = entry["distance"]
            routes.append(route)

        if protocol:
            routes = [r for r in routes if r["protocol"] == protocol.lower()]

        return json.dumps({
            "device": device_name,
            "routes": routes,
            "total": len(routes),
        }, indent=2)

    except Exception as exc:
        log_event(action="get_routing_table", details=str(exc), status="error")
        return json.dumps({"error": f"Failed to get routing table for {device_name}: {exc}"})


async def get_neighbors(device_name: str, protocol: str = "all") -> str:
    """
    Get routing protocol neighbor status (OSPF and/or BGP).

    Returns routing protocol neighbors — NOT L2 discovery neighbors.
    Use ``lldp_neighbors`` for L2 topology information.

    Args:
        device_name: Device name from inventory
        protocol: "bgp", "ospf", or "all" (default)

    Returns:
        JSON with OSPF and BGP neighbor details

    Example response::

        {
          "device": "R1",
          "ospf_neighbors": [
            {"neighbor_id": "198.51.100.2", "state": "FULL/DR",
             "interface": "GigabitEthernet2", "uptime": "14d06h"}
          ],
          "bgp_neighbors": [
            {"neighbor": "198.51.100.2", "as": 65000, "state": "Established",
             "prefixes_received": 5, "uptime": "14d06h"}
          ]
        }
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "ospf_neighbors": [
                {
                    "neighbor_id": "198.51.100.2", "state": "FULL/DR",
                    "interface": "GigabitEthernet2", "uptime": "14d06h",
                },
            ],
            "bgp_neighbors": [
                {
                    "neighbor": "198.51.100.2", "as": 65000,
                    "state": "Established",
                    "prefixes_received": 5, "uptime": "14d06h",
                },
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    result = {"device": device_name}

    try:
        from core.scrapli_manager import send_command

        if protocol in ("ospf", "all"):
            raw = await throttled(send_command(device_name, "show ip ospf neighbor"))
            result["ospf_neighbors"] = _parse_ospf_neighbors(raw)

        if protocol in ("bgp", "all"):
            raw = await throttled(send_command(device_name, "show ip bgp summary"))
            result["bgp_neighbors"] = _parse_bgp_summary(raw)

        return json.dumps(result, indent=2)

    except Exception as exc:
        log_event(action="get_neighbors", details=str(exc), status="error")
        return json.dumps({"error": f"Failed to get neighbors for {device_name}: {exc}"})


def _parse_ospf_neighbors(raw: str) -> list[dict]:
    """Parse ``show ip ospf neighbor`` output."""
    neighbors = []
    for line in raw.splitlines():
        # Neighbor ID  Pri  State  Dead Time  Address  Interface
        match = re.match(
            r'^(\d+\.\d+\.\d+\.\d+)\s+'  # neighbor_id
            r'(\d+)\s+'                    # priority
            r'(\S+)\s+'                    # state (e.g. FULL/DR)
            r'(\S+)\s+'                    # dead time
            r'(\d+\.\d+\.\d+\.\d+)\s+'    # address
            r'(\S+)',                       # interface
            line,
        )
        if match:
            neighbors.append({
                "neighbor_id": match.group(1),
                "priority": int(match.group(2)),
                "state": match.group(3),
                "dead_time": match.group(4),
                "address": match.group(5),
                "interface": match.group(6),
            })
    return neighbors


def _parse_bgp_summary(raw: str) -> list[dict]:
    """Parse ``show ip bgp summary`` output."""
    neighbors = []
    in_table = False

    for line in raw.splitlines():
        line = line.strip()
        # Detect start of neighbor table
        if line.startswith("Neighbor"):
            in_table = True
            continue
        if not in_table or not line:
            continue

        parts = line.split()
        if len(parts) >= 10:
            neighbor_ip = parts[0]
            # Validate it looks like an IP
            if not re.match(r'\d+\.\d+\.\d+\.\d+', neighbor_ip):
                continue

            try:
                remote_as = int(parts[2])
            except (ValueError, IndexError):
                remote_as = 0

            state_or_pfx = parts[-1]
            try:
                prefixes = int(state_or_pfx)
                state = "Established"
            except ValueError:
                prefixes = 0
                state = state_or_pfx

            uptime = parts[8] if len(parts) > 8 else ""

            neighbors.append({
                "neighbor": neighbor_ip,
                "as": remote_as,
                "state": state,
                "prefixes_received": prefixes,
                "uptime": uptime,
            })

    return neighbors


TOOLS = [
    {"fn": get_routing_table, "name": "get_routing_table", "category": "routing"},
    {"fn": get_neighbors, "name": "get_neighbors", "category": "routing"},
]
