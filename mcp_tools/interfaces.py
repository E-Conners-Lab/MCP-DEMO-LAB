"""
Interface management MCP tools.

- get_interface_status: Get all interface statuses via ``show ip interface brief``
- get_arp_table: Get ARP table entries (optional VRF filter)
- get_mac_table: Get MAC address table (optional VLAN filter)

Public API note: ``get_interface_status`` returns ALL interfaces for the
device.
"""

import json
import logging

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode, throttled

logger = logging.getLogger(__name__)


async def get_interface_status(device_name: str) -> str:
    """
    Get interface status and statistics for all interfaces on a device.

    Uses ``show ip interface brief`` for IOS-XE devices.
    Returns all interfaces (not a specific one) — use this to get a
    full picture of interface state.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with interface names, status, protocol, IP, and description

    Example response::

        {
          "device": "R1",
          "interfaces": [
            {"name": "GigabitEthernet1", "status": "up", "protocol": "up",
             "ip": "10.255.255.11/24", "description": "MGMT"},
            ...
          ]
        }
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "interfaces": [
                {
                    "name": "GigabitEthernet1", "status": "up",
                    "protocol": "up", "ip": "10.255.255.11/24",
                    "description": "MGMT",
                },
                {
                    "name": "GigabitEthernet2", "status": "up",
                    "protocol": "up", "ip": "10.0.12.1/30",
                    "description": "to R2",
                },
                {
                    "name": "GigabitEthernet3", "status": "down",
                    "protocol": "down", "ip": "unassigned",
                    "description": "",
                },
                {
                    "name": "Loopback0", "status": "up",
                    "protocol": "up", "ip": "198.51.100.1/32",
                    "description": "Router-ID",
                },
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.scrapli_manager import send_command
        from core.unified_parser import parse_show_ip_interface_brief

        raw = await throttled(send_command(device_name, "show ip interface brief"))
        parsed = parse_show_ip_interface_brief(raw)

        interfaces = []
        for entry in parsed:
            interfaces.append({
                "name": entry.get("interface", ""),
                "status": entry.get("status", ""),
                "protocol": entry.get("protocol", ""),
                "ip": entry.get("ip_address", "unassigned"),
                "description": "",
            })

        return json.dumps({"device": device_name, "interfaces": interfaces}, indent=2)

    except Exception as exc:
        log_event(action="get_interface_status", details=str(exc), status="error")
        return json.dumps({"error": f"Failed to get interfaces for {device_name}: {exc}"})


async def get_arp_table(device_name: str, vrf: str = None) -> str:
    """
    Get the ARP table from a device.

    Args:
        device_name: Device name from inventory
        vrf: Optional VRF name to filter ARP entries

    Returns:
        JSON with ARP entries (IP, MAC, interface, age)

    Example response::

        {
          "device": "R1",
          "entries": [
            {"ip": "10.0.12.2", "mac": "5254.0012.0002",
             "interface": "GigabitEthernet2", "age": "5 min"}
          ],
          "total": 1
        }
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "entries": [
                {
                    "ip": "10.0.12.2", "mac": "5254.0012.0002",
                    "interface": "GigabitEthernet2", "age": "5 min",
                },
                {
                    "ip": "10.255.255.1", "mac": "5254.00ff.0001",
                    "interface": "GigabitEthernet1", "age": "0 min",
                },
            ],
            "total": 2,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.scrapli_manager import send_command
        from core.unified_parser import parse_cli_output

        command = "show ip arp"
        if vrf:
            command = f"show ip arp vrf {vrf}"

        raw = await throttled(send_command(device_name, command))
        parsed = parse_cli_output(command, raw, platform="cisco_ios")

        entries = []
        for row in parsed:
            entries.append({
                "ip": row.get("address", row.get("ip", "")),
                "mac": row.get("mac", row.get("hardware", "")),
                "interface": row.get("interface", ""),
                "age": row.get("age", ""),
            })

        return json.dumps({
            "device": device_name,
            "entries": entries,
            "total": len(entries),
        }, indent=2)

    except Exception as exc:
        log_event(action="get_arp_table", details=str(exc), status="error")
        return json.dumps({"error": f"Failed to get ARP table for {device_name}: {exc}"})


async def get_mac_table(device_name: str, vlan: int = None) -> str:
    """
    Get the MAC address table from a switch.

    Args:
        device_name: Device name from inventory
        vlan: Optional VLAN ID to filter entries

    Returns:
        JSON with MAC entries (VLAN, MAC, type, port)

    Example response::

        {
          "device": "Switch-R1",
          "entries": [
            {"vlan": 1, "mac": "5254.0012.0001", "type": "dynamic", "port": "Gi0/1"}
          ],
          "total": 1
        }
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "entries": [
                {"vlan": 1, "mac": "5254.0012.0001", "type": "dynamic", "port": "Gi0/1"},
                {"vlan": 10, "mac": "5254.0012.0002", "type": "dynamic", "port": "Gi0/2"},
            ],
            "total": 2,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.scrapli_manager import send_command
        from core.unified_parser import parse_cli_output

        command = "show mac address-table"
        if vlan is not None:
            command = f"show mac address-table vlan {vlan}"

        raw = await throttled(send_command(device_name, command))
        parsed = parse_cli_output(command, raw, platform="cisco_ios")

        entries = []
        for row in parsed:
            entry_vlan = row.get("vlan", "")
            try:
                entry_vlan = int(entry_vlan)
            except (ValueError, TypeError):
                pass
            entries.append({
                "vlan": entry_vlan,
                "mac": row.get("destination_address", row.get("mac", "")),
                "type": row.get("type", ""),
                "port": row.get("destination_port", row.get("ports", "")),
            })

        return json.dumps({
            "device": device_name,
            "entries": entries,
            "total": len(entries),
        }, indent=2)

    except Exception as exc:
        log_event(action="get_mac_table", details=str(exc), status="error")
        return json.dumps({"error": f"Failed to get MAC table for {device_name}: {exc}"})


TOOLS = [
    {"fn": get_interface_status, "name": "get_interface_status", "category": "interfaces"},
    {"fn": get_arp_table, "name": "get_arp_table", "category": "interfaces"},
    {"fn": get_mac_table, "name": "get_mac_table", "category": "interfaces"},
]
