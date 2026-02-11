"""
NETCONF MCP tools.

- get_interfaces_netconf: Get interface data via NETCONF (ietf-interfaces)
- get_bgp_neighbors_netconf: Get BGP state via NETCONF (openconfig-bgp)
- get_netconf_capabilities: List device NETCONF capabilities

Uses ``asyncio.to_thread`` for sync NETCONF calls via ncclient.
"""

import json
import logging

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode

logger = logging.getLogger(__name__)

# YANG filter for ietf-interfaces
IETF_INTERFACES_FILTER = """
<interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
"""

# YANG filter for openconfig BGP
OPENCONFIG_BGP_FILTER = """
<bgp xmlns="http://openconfig.net/yang/bgp"/>
"""


async def get_interfaces_netconf(device_name: str) -> str:
    """
    Get interface operational data via NETCONF (YANG model).

    Uses ietf-interfaces YANG model for accurate admin/oper status.
    More reliable than CLI parsing for structured data.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with interface operational data from YANG model
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "source": "NETCONF (ietf-interfaces)",
            "interfaces": [
                {
                    "name": "GigabitEthernet1", "admin_status": "up",
                    "oper_status": "up", "mtu": 1500,
                },
                {
                    "name": "GigabitEthernet2", "admin_status": "up",
                    "oper_status": "up", "mtu": 1500,
                },
                {"name": "Loopback0", "admin_status": "up", "oper_status": "up", "mtu": 1500},
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        import defusedxml.ElementTree as ET

        from core.netconf_client import get_operational

        xml_str = await get_operational(device_name, IETF_INTERFACES_FILTER)

        root = ET.fromstring(xml_str)
        ns = {"if": "urn:ietf:params:xml:ns:yang:ietf-interfaces"}

        interfaces = []
        for iface in root.iter("{urn:ietf:params:xml:ns:yang:ietf-interfaces}interface"):
            name_el = iface.find("if:name", ns)
            admin_el = iface.find("if:admin-status", ns)
            oper_el = iface.find("if:oper-status", ns)
            mtu_el = iface.find("if:mtu", ns)

            interfaces.append({
                "name": name_el.text if name_el is not None else "",
                "admin_status": admin_el.text if admin_el is not None else "unknown",
                "oper_status": oper_el.text if oper_el is not None else "unknown",
                "mtu": int(mtu_el.text) if mtu_el is not None else None,
            })

        return json.dumps({
            "device": device_name,
            "source": "NETCONF (ietf-interfaces)",
            "interfaces": interfaces,
        }, indent=2)

    except Exception as exc:
        log_event(action="get_interfaces_netconf", details=str(exc), status="error")
        return json.dumps({"error": f"NETCONF interface query failed for {device_name}: {exc}"})


async def get_bgp_neighbors_netconf(device_name: str) -> str:
    """
    Get BGP neighbor state via NETCONF.

    Uses OpenConfig or Cisco native YANG models for BGP state.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with BGP neighbor details from YANG model
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "source": "NETCONF (openconfig-bgp)",
            "neighbors": [
                {
                    "neighbor": "198.51.100.2",
                    "remote_as": 65000,
                    "state": "ESTABLISHED",
                    "prefixes_received": 5,
                    "uptime_seconds": 1234567,
                },
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        import defusedxml.ElementTree as ET

        from core.netconf_client import get_operational

        xml_str = await get_operational(device_name, OPENCONFIG_BGP_FILTER)
        root = ET.fromstring(xml_str)

        oc = "http://openconfig.net/yang/bgp"
        neighbors = []

        for nbr in root.iter(f"{{{oc}}}neighbor"):
            addr_el = nbr.find(f"{{{oc}}}neighbor-address")
            state_el = nbr.find(f".//{{{oc}}}session-state")
            as_el = nbr.find(f".//{{{oc}}}peer-as")
            pfx_el = nbr.find(f".//{{{oc}}}received")

            neighbors.append({
                "neighbor": addr_el.text if addr_el is not None else "",
                "remote_as": int(as_el.text) if as_el is not None else 0,
                "state": state_el.text if state_el is not None else "unknown",
                "prefixes_received": int(pfx_el.text) if pfx_el is not None else 0,
            })

        return json.dumps({
            "device": device_name,
            "source": "NETCONF (openconfig-bgp)",
            "neighbors": neighbors,
        }, indent=2)

    except Exception as exc:
        log_event(action="get_bgp_neighbors_netconf", details=str(exc), status="error")
        return json.dumps({"error": f"NETCONF BGP query failed for {device_name}: {exc}"})


async def get_netconf_capabilities(device_name: str) -> str:
    """
    List NETCONF capabilities supported by a device.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with list of NETCONF capabilities (YANG models)
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "capabilities_count": 5,
            "capabilities": [
                "urn:ietf:params:xml:ns:yang:ietf-interfaces",
                "urn:ietf:params:xml:ns:yang:ietf-ip",
                "urn:ietf:params:xml:ns:netconf:base:1.1",
                "http://openconfig.net/yang/bgp",
                "http://cisco.com/ns/yang/Cisco-IOS-XE-native",
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.netconf_client import get_capabilities

        caps = await get_capabilities(device_name)
        return json.dumps({
            "device": device_name,
            "capabilities_count": len(caps),
            "capabilities": caps,
        }, indent=2)

    except Exception as exc:
        log_event(action="get_netconf_capabilities", details=str(exc), status="error")
        return json.dumps({"error": f"NETCONF capabilities query failed for {device_name}: {exc}"})


TOOLS = [
    {"fn": get_interfaces_netconf, "name": "get_interfaces_netconf", "category": "netconf"},
    {"fn": get_bgp_neighbors_netconf, "name": "get_bgp_neighbors_netconf", "category": "netconf"},
    {"fn": get_netconf_capabilities, "name": "get_netconf_capabilities", "category": "netconf"},
]
