"""LLDP topology discovery helpers.

Provides functions to query LLDP neighbor information from network
devices and build topology maps.  Delegates to ``core.scrapli_manager``
for CLI interaction.
"""

import logging
import re

from config.devices import DEVICES, is_containerlab_device

logger = logging.getLogger(__name__)


async def discover_lldp_neighbors(device_name: str) -> list[dict]:
    """Get LLDP neighbors for a device.

    Returns list of dicts with local_port, remote_device, remote_port,
    and capabilities.
    """
    device = DEVICES.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")

    if is_containerlab_device(device_name):
        return await _lldp_via_containerlab(device_name)

    from core.scrapli_manager import send_command
    raw = await send_command(device_name, "show lldp neighbors detail")
    return _parse_lldp_detail(raw)


async def discover_lldp_topology() -> dict:
    """Discover full network topology via LLDP across all devices.

    Returns dict with nodes (list of device names) and edges (list of links).
    """
    nodes = list(DEVICES.keys())
    edges = []
    seen_links = set()

    for device_name in nodes:
        try:
            neighbors = await discover_lldp_neighbors(device_name)
            for nbr in neighbors:
                # Deduplicate bidirectional links
                link = tuple(sorted([device_name, nbr.get("remote_device", "")]))
                if link not in seen_links and link[0] != link[1]:
                    seen_links.add(link)
                    edges.append({
                        "from": device_name,
                        "to": nbr["remote_device"],
                        "local_port": nbr.get("local_port", ""),
                        "remote_port": nbr.get("remote_port", ""),
                    })
        except Exception as exc:
            logger.warning("LLDP discovery failed for %s: %s", device_name, exc)

    return {
        "nodes": nodes,
        "edges": edges,
        "device_count": len(nodes),
        "link_count": len(edges),
    }


async def check_lldp_enabled(device_name: str) -> dict:
    """Check LLDP status on a device.

    Returns dict with lldp_enabled, hold_time, timer.
    """
    from core.scrapli_manager import send_command
    raw = await send_command(device_name, "show lldp")

    enabled = "LLDP is not enabled" not in raw
    hold_time = 120
    timer = 30

    # Parse hold time and timer from output
    for line in raw.splitlines():
        if "Hold time" in line:
            match = re.search(r'(\d+)', line)
            if match:
                hold_time = int(match.group(1))
        if "Timer" in line or "Reinit" in line:
            match = re.search(r'(\d+)', line)
            if match:
                timer = int(match.group(1))

    return {
        "device": device_name,
        "lldp_enabled": enabled,
        "hold_time": hold_time,
        "timer": timer,
    }


def _parse_lldp_detail(raw: str) -> list[dict]:
    """Parse ``show lldp neighbors detail`` output."""
    neighbors = []
    current = {}

    for line in raw.splitlines():
        line = line.strip()
        if "Local Intf" in line or "Local Port id" in line:
            if current:
                neighbors.append(current)
            current = {}
            match = re.search(r':\s*(\S+)', line)
            if match:
                current["local_port"] = match.group(1)
        elif "System Name" in line:
            match = re.search(r':\s*(.+)', line)
            if match:
                current["remote_device"] = match.group(1).strip()
        elif "Port id" in line or "Port Description" in line:
            if "remote_port" not in current:
                match = re.search(r':\s*(\S+)', line)
                if match:
                    current["remote_port"] = match.group(1)
        elif "System Capabilities" in line:
            match = re.search(r':\s*(.+)', line)
            if match:
                current["capabilities"] = match.group(1).strip()

    if current:
        neighbors.append(current)

    return neighbors


async def _lldp_via_containerlab(device_name: str) -> list[dict]:
    """Get LLDP info from a containerlab container via docker exec."""
    from core.containerlab import run_command

    device = DEVICES.get(device_name)
    container = device.get("container", "")
    if not container:
        return []

    try:
        raw = await run_command(container, "lldpctl -f keyvalue")
        return _parse_lldpctl_keyvalue(raw)
    except Exception as exc:
        logger.warning("LLDP via containerlab failed for %s: %s", device_name, exc)
        return []


def _parse_lldpctl_keyvalue(raw: str) -> list[dict]:
    """Parse ``lldpctl -f keyvalue`` output."""
    neighbors = []
    current = {}

    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()

        if "chassis.name" in key:
            if current:
                neighbors.append(current)
            current = {"remote_device": value}
        elif "port.ifname" in key:
            if "local_port" not in current:
                current["local_port"] = value
            else:
                current["remote_port"] = value
        elif "port.descr" in key and "remote_port" not in current:
            current["remote_port"] = value

    if current:
        neighbors.append(current)

    return neighbors
