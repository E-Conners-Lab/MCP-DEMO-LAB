"""
Device management MCP tools.

Core device interaction:
- get_devices: List all devices in inventory
- send_command: Execute show commands
- send_config: Apply configuration changes
- health_check: Check single device health
- health_check_all: Check all devices in parallel
"""

import asyncio
import json
import logging
import re

from config.devices import DEVICES, is_containerlab_device
from core import log_event
from mcp_tools._shared import DEMO_DEVICES, DEMO_HEALTH, is_demo_mode, throttled

logger = logging.getLogger(__name__)


async def get_devices() -> str:
    """
    List all devices in the inventory with their connection details.

    Returns:
        JSON with device names, types, and management IPs

    Example response:
        {"devices": {"R1": {"device_type": "cisco_xe", "host": "10.255.255.11"}, ...}}
    """
    if is_demo_mode():
        return json.dumps({"devices": DEMO_DEVICES, "count": len(DEMO_DEVICES)}, indent=2)

    device_list = {}
    for name, config in DEVICES.items():
        device_list[name] = {
            "device_type": config.get("device_type"),
            "host": config.get("host"),
        }

    return json.dumps({"devices": device_list, "count": len(device_list)}, indent=2)


async def send_command(device_name: str, command: str) -> str:
    """
    Execute a show command on a network device and return the output.

    Args:
        device_name: Device name from inventory (e.g., "R1", "Switch-R1")
        command: Show command to execute (e.g., "show ip route", "show interfaces")

    Returns:
        Command output as text, or error message

    Examples:
        send_command("R1", "show ip route")
        send_command("Switch-R1", "show vlan brief")
        send_command("R1", "show ip ospf neighbor")
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "command": command,
            "output": f"[DEMO] Mock output for '{command}' on {device_name}\n"
                      f"This is demo mode. Connect real devices to see actual output.",
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    log_event(action="send_command", details=f"{device_name}: {command}", status="start")

    try:
        device_type = device.get("device_type", "cisco_xe")

        if is_containerlab_device(device_name):
            from core.containerlab import run_command
            container = device.get("container", "")
            if not container:
                return json.dumps({"error": f"No container name configured for {device_name}"})
            output = await run_command(container, command)
        else:
            from core.scrapli_manager import send_command as scrapli_send
            output = await throttled(
                scrapli_send(device_name, command, device_type=device_type)
            )

        return json.dumps({
            "device": device_name,
            "command": command,
            "output": output,
        }, indent=2)

    except Exception as exc:
        log_event(action="send_command", details=str(exc), status="error")
        return json.dumps({"error": f"Command failed on {device_name}: {exc}"})


async def send_config(device_name: str, commands: str) -> str:
    """
    Apply configuration commands to a network device.

    Args:
        device_name: Device name from inventory
        commands: Configuration commands (newline-separated for multiple)

    Returns:
        JSON with success status and device response

    Examples:
        send_config("R1", "interface Loopback99\\ndescription Test")
        send_config("R1", "no interface Loopback99")
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "status": "success",
            "message": f"[DEMO] Config applied to {device_name}",
            "commands_sent": commands.split("\n"),
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    cmd_count = len(commands.split(chr(10)))
    log_event(action="send_config", details=f"{device_name}: {cmd_count} commands", status="start")

    try:
        cmd_list = [c.strip() for c in commands.split("\n") if c.strip()]

        from core.scrapli_manager import send_config as scrapli_cfg
        output = await throttled(scrapli_cfg(device_name, cmd_list))

        return json.dumps({
            "device": device_name,
            "status": "success",
            "commands_sent": cmd_list,
            "output": output,
        }, indent=2)

    except Exception as exc:
        log_event(action="send_config", details=str(exc), status="error")
        return json.dumps({"error": f"Config push failed on {device_name}: {exc}"})


async def health_check(device_name: str) -> str:
    """
    Check the health of a single device.

    Returns CPU usage, memory usage, uptime, and interface status.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with device health metrics
    """
    if is_demo_mode():
        if device_name in DEMO_HEALTH:
            return json.dumps(DEMO_HEALTH[device_name], indent=2)
        return json.dumps({"error": f"Device '{device_name}' not found in demo inventory"})

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        result = await _collect_health(device_name)
        return json.dumps(result, indent=2)

    except Exception as exc:
        log_event(action="health_check", details=str(exc), status="error")
        return json.dumps({
            "device": device_name,
            "status": "unreachable",
            "reachable": False,
            "error": str(exc),
        })


async def health_check_all() -> str:
    """
    Check the health of all devices in the inventory in parallel.

    Returns a summary of all device health statuses, with details
    for any devices that have issues.

    Returns:
        JSON with health status for every device
    """
    if is_demo_mode():
        results = list(DEMO_HEALTH.values())
        healthy = sum(1 for r in results if r["status"] == "healthy")
        return json.dumps({
            "summary": {
                "total": len(results),
                "healthy": healthy,
                "warning": len(results) - healthy,
                "critical": 0,
                "unreachable": 0,
            },
            "devices": results,
        }, indent=2)

    # Real: check all devices in parallel
    device_names = list(DEVICES.keys())
    if not device_names:
        return json.dumps({
            "summary": {"total": 0, "healthy": 0, "warning": 0, "critical": 0, "unreachable": 0},
            "devices": [],
        }, indent=2)

    tasks = [_collect_health(name) for name in device_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    device_results = []
    for name, result in zip(device_names, results):
        if isinstance(result, Exception):
            device_results.append({
                "device": name,
                "status": "unreachable",
                "reachable": False,
                "error": str(result),
            })
        else:
            device_results.append(result)

    healthy = sum(1 for r in device_results if r.get("status") == "healthy")
    warning = sum(1 for r in device_results if r.get("status") == "warning")
    critical = sum(1 for r in device_results if r.get("status") == "critical")
    unreachable = sum(1 for r in device_results if r.get("status") == "unreachable")

    return json.dumps({
        "summary": {
            "total": len(device_results),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "unreachable": unreachable,
        },
        "devices": device_results,
    }, indent=2)


async def _collect_health(device_name: str) -> dict:
    """Collect health metrics for a single device."""
    device = DEVICES.get(device_name)
    if is_containerlab_device(device_name):
        from core.containerlab import check_health
        container = device.get("container", "")
        result = await check_health(container)
        return {
            "device": device_name,
            "status": "healthy" if result["reachable"] else "unreachable",
            "reachable": result["reachable"],
        }

    from core.scrapli_manager import send_command as scrapli_send

    # Gather CPU, memory, uptime, interfaces in parallel
    cpu_task = throttled(scrapli_send(device_name, "show processes cpu | include CPU utilization"))
    mem_cmd = "show platform software status control-processor brief"
    mem_task = throttled(scrapli_send(device_name, mem_cmd))
    uptime_task = throttled(scrapli_send(device_name, "show version | include uptime"))
    intf_task = throttled(scrapli_send(device_name, "show ip interface brief"))

    cpu_raw, mem_raw, uptime_raw, intf_raw = await asyncio.gather(
        cpu_task, mem_task, uptime_task, intf_task,
        return_exceptions=True,
    )

    # Parse results
    cpu_pct = _parse_cpu(cpu_raw if isinstance(cpu_raw, str) else "")
    mem_pct = _parse_memory(mem_raw if isinstance(mem_raw, str) else "")
    uptime = _parse_uptime(uptime_raw if isinstance(uptime_raw, str) else "")
    intf_counts = _parse_interface_counts(intf_raw if isinstance(intf_raw, str) else "")

    status = "healthy"
    if cpu_pct and int(cpu_pct.rstrip("%")) > 80:
        status = "critical"
    elif mem_pct and int(mem_pct.rstrip("%")) > 80:
        status = "warning"
    elif intf_counts.get("down", 0) > 0:
        status = "warning"

    return {
        "device": device_name,
        "status": status,
        "reachable": True,
        "cpu_usage": cpu_pct or "unknown",
        "memory_usage": mem_pct or "unknown",
        "uptime": uptime or "unknown",
        "interfaces": intf_counts,
    }


def _parse_cpu(raw: str) -> str:
    """Extract CPU usage percentage from show processes cpu output."""
    match = re.search(r'five minutes:\s*(\d+)%', raw)
    if match:
        return f"{match.group(1)}%"
    match = re.search(r'(\d+)%', raw)
    return f"{match.group(1)}%" if match else ""


def _parse_memory(raw: str) -> str:
    """Extract memory usage percentage."""
    match = re.search(r'(\d+)%', raw)
    return f"{match.group(1)}%" if match else ""


def _parse_uptime(raw: str) -> str:
    """Extract uptime string."""
    match = re.search(r'uptime is (.+)', raw)
    return match.group(1).strip() if match else ""


def _parse_interface_counts(raw: str) -> dict:
    """Count up/down interfaces from show ip interface brief."""
    total = 0
    up = 0
    down = 0
    for line in raw.splitlines():
        # Skip header lines
        if "Interface" in line and "Status" in line:
            continue
        parts = line.split()
        if len(parts) >= 6:
            total += 1
            if parts[-1].lower() == "up":
                up += 1
            else:
                down += 1
    return {"total": total, "up": up, "down": down}


# =============================================================================
# Tool Registry
# =============================================================================

TOOLS = [
    {"fn": get_devices, "name": "get_devices", "category": "device"},
    {"fn": send_command, "name": "send_command", "category": "device"},
    {"fn": send_config, "name": "send_config", "category": "device"},
    {"fn": health_check, "name": "health_check", "category": "device"},
    {"fn": health_check_all, "name": "health_check_all", "category": "device"},
]
