"""Netmiko connection manager for legacy device interaction.

Provides synchronous Netmiko helpers wrapped in ``asyncio.to_thread``
for compatibility with the async MCP server.

Used as a fallback when Scrapli doesn't support the platform.
"""

import asyncio
import logging

from config.devices import DEVICES, PASSWORD, USERNAME

logger = logging.getLogger(__name__)


def _build_netmiko_params(device_name: str) -> dict:
    """Build a Netmiko connection parameter dict for a device."""
    device = DEVICES.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")

    # Map our device_type to Netmiko device_type
    dtype = device.get("device_type", "cisco_ios")
    netmiko_map = {
        "cisco_xe": "cisco_ios",
        "juniper_junos": "juniper_junos",
        "aruba_aoscx": "aruba_os",
        "linux": "linux",
        "containerlab_linux": "linux",
        "containerlab_frr": "linux",
        "containerlab_srlinux": "linux",
    }

    return {
        "device_type": netmiko_map.get(dtype, "cisco_ios"),
        "host": device.get("host", ""),
        "username": device.get("username", USERNAME),
        "password": device.get("password", PASSWORD),
    }


async def send_command(device_name: str, command: str) -> str:
    """Send a show command via Netmiko (runs in a thread)."""
    from netmiko import ConnectHandler

    params = _build_netmiko_params(device_name)

    def _run():
        with ConnectHandler(**params) as conn:
            return conn.send_command(command)

    return await asyncio.to_thread(_run)


async def send_config(device_name: str, commands: list[str]) -> str:
    """Send configuration commands via Netmiko (runs in a thread)."""
    from netmiko import ConnectHandler

    params = _build_netmiko_params(device_name)

    def _run():
        with ConnectHandler(**params) as conn:
            return conn.send_config_set(commands)

    return await asyncio.to_thread(_run)
