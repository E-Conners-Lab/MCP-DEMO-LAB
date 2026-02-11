"""
Bulk operations MCP tools.

- bulk_command: Run the same command across multiple devices
- ping_sweep: Ping explicit target IPs from a device
- traceroute: Trace route to a destination from a device

Signature notes:
- ``ping_sweep`` takes an explicit list of targets (not a subnet).
  Subnet-based sweep is intentionally unsupported — subnets can be huge,
  and explicit targets are safer for an MCP tool.
- ``traceroute`` requires both device_name and destination.
"""

import asyncio
import json
import logging
import re

from config.devices import DEVICES, is_containerlab_device
from core import log_event
from mcp_tools._shared import is_demo_mode, throttled

logger = logging.getLogger(__name__)


async def bulk_command(command: str, device_names: str = None, device_type: str = None) -> str:
    """
    Execute a command across multiple devices in parallel.

    Args:
        command: Show command to execute on all devices
        device_names: Comma-separated device names (default: all devices)
        device_type: Filter by device type (e.g., "cisco_xe")

    Returns:
        JSON with command output from each device
    """
    if is_demo_mode():
        return json.dumps({
            "command": command,
            "results": {
                "R1": {"status": "success", "output": f"[DEMO] {command} output for R1"},
                "R2": {"status": "success", "output": f"[DEMO] {command} output for R2"},
                "R3": {"status": "success", "output": f"[DEMO] {command} output for R3"},
            },
            "summary": {"total": 3, "success": 3, "failed": 0},
        }, indent=2)

    # Determine target devices
    if device_names:
        targets = [n.strip() for n in device_names.split(",")]
    elif device_type:
        targets = [
            name for name, conf in DEVICES.items()
            if conf.get("device_type") == device_type
        ]
    else:
        targets = list(DEVICES.keys())

    if not targets:
        return json.dumps({"error": "No target devices found"})

    log_event(
        action="bulk_command",
        details=f"{command} on {len(targets)} devices",
        status="start",
    )

    # Execute in parallel
    tasks = [_send_command_raw(name, command) for name in targets]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results = {}
    success = 0
    failed = 0
    for name, result in zip(targets, raw_results):
        if isinstance(result, Exception):
            results[name] = {"status": "failed", "error": str(result)}
            failed += 1
        else:
            results[name] = {"status": "success", "output": result}
            success += 1

    return json.dumps({
        "command": command,
        "results": results,
        "summary": {"total": len(targets), "success": success, "failed": failed},
    }, indent=2)


async def _send_command_raw(device_name: str, command: str) -> str:
    """Send a single command to a device. Returns raw output string."""
    device = DEVICES.get(device_name)
    if not device:
        raise ValueError(f"Device '{device_name}' not found")

    if is_containerlab_device(device_name):
        from core.containerlab import run_command
        container = device.get("container", "")
        return await run_command(container, command)

    from core.scrapli_manager import send_command as scrapli_send
    device_type = device.get("device_type", "cisco_xe")
    return await throttled(scrapli_send(device_name, command, device_type=device_type))


async def ping_sweep(device_name: str, targets: str, count: int = 3) -> str:
    """
    Ping a list of target IPs from a network device.

    Subnet-based sweep is intentionally not supported — subnets can be
    arbitrarily large and explicit targets are safer for an MCP tool.

    Args:
        device_name: Device to ping from
        targets: Comma-separated target IPs (e.g., "10.0.0.1,10.0.0.2,10.0.0.3")
        count: Number of ping packets per target (default: 3)

    Returns:
        JSON with reachable/unreachable lists and summary

    Example call:
        ping_sweep("R1", "10.0.12.2,10.0.23.2,10.0.34.2", count=5)

    Example response::

        {
          "device": "R1",
          "reachable": ["10.0.12.2", "10.0.23.2"],
          "unreachable": ["10.0.34.2"],
          "summary": {"total": 3, "reachable": 2, "unreachable": 1}
        }
    """
    if is_demo_mode():
        target_list = [t.strip() for t in targets.split(",")]
        # In demo mode, mark first 60% as reachable
        split_idx = max(1, int(len(target_list) * 0.6))
        return json.dumps({
            "device": device_name,
            "reachable": target_list[:split_idx],
            "unreachable": target_list[split_idx:],
            "summary": {
                "total": len(target_list),
                "reachable": split_idx,
                "unreachable": len(target_list) - split_idx,
            },
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        return json.dumps({"error": "No targets specified"})

    log_event(
        action="ping_sweep",
        details=f"{device_name}: {len(target_list)} targets",
        status="start",
    )

    reachable = []
    unreachable = []

    for target in target_list:
        try:
            cmd = f"ping {target} repeat {count}"
            output = await _send_command_raw(device_name, cmd)
            if "Success rate is 0" in output or "0 percent" in output.lower():
                unreachable.append(target)
            else:
                reachable.append(target)
        except Exception:
            unreachable.append(target)

    return json.dumps({
        "device": device_name,
        "reachable": reachable,
        "unreachable": unreachable,
        "summary": {
            "total": len(target_list),
            "reachable": len(reachable),
            "unreachable": len(unreachable),
        },
    }, indent=2)


async def traceroute(device_name: str, destination: str, source: str = None) -> str:
    """
    Trace route to a destination from a network device.

    Args:
        device_name: Source device name from inventory
        destination: Target IP or hostname
        source: Optional source IP or interface for the traceroute

    Returns:
        JSON with hop-by-hop path to destination

    Example call:
        traceroute("R1", "198.51.100.3", source="Loopback0")

    Example response::

        {
          "device": "R1",
          "destination": "198.51.100.3",
          "hops": [
            {"hop": 1, "ip": "10.0.12.2", "rtt_ms": "2"},
            {"hop": 2, "ip": "198.51.100.3", "rtt_ms": "4"}
          ]
        }
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "destination": destination,
            "hops": [
                {"hop": 1, "ip": "10.0.12.2", "hostname": "R2", "rtt_ms": 2.1},
                {"hop": 2, "ip": "10.0.23.2", "hostname": "R3", "rtt_ms": 4.3},
                {"hop": 3, "ip": destination, "hostname": "*", "rtt_ms": 6.7},
            ],
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    log_event(
        action="traceroute",
        details=f"{device_name} → {destination}",
        status="start",
    )

    try:
        cmd = f"traceroute {destination}"
        if source:
            cmd += f" source {source}"

        output = await _send_command_raw(device_name, cmd)
        hops = _parse_traceroute(output)

        return json.dumps({
            "device": device_name,
            "destination": destination,
            "source": source,
            "hops": hops,
        }, indent=2)

    except Exception as exc:
        log_event(action="traceroute", details=str(exc), status="error")
        return json.dumps({"error": f"Traceroute failed from {device_name}: {exc}"})


def _parse_traceroute(raw: str) -> list[dict]:
    """Parse traceroute output into structured hop list."""
    hops = []
    for line in raw.splitlines():
        # Match lines like: "  1  10.0.12.2 4 msec 4 msec 4 msec"
        match = re.match(r'^\s*(\d+)\s+(.+)', line)
        if not match:
            continue

        hop_num = int(match.group(1))
        rest = match.group(2).strip()

        # Extract IP and RTT
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', rest)
        rtt_match = re.search(r'(\d+)\s*msec', rest)

        if ip_match:
            hop = {
                "hop": hop_num,
                "ip": ip_match.group(1),
            }
            if rtt_match:
                hop["rtt_ms"] = rtt_match.group(1)
            hops.append(hop)
        elif "* * *" in rest:
            hops.append({"hop": hop_num, "ip": "*", "rtt_ms": "*"})

    return hops


TOOLS = [
    {"fn": bulk_command, "name": "bulk_command", "category": "operations"},
    {"fn": ping_sweep, "name": "ping_sweep", "category": "operations"},
    {"fn": traceroute, "name": "traceroute", "category": "operations"},
]
