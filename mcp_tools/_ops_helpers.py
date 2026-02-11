"""Shared helpers for operations-related MCP tools.

Small utility functions used across device, operations, interfaces,
and routing tool modules.
"""

from config.devices import DEVICES


def is_cisco_device(device_name: str) -> bool:
    """Check if a device is Cisco IOS-XE."""
    device = DEVICES.get(device_name)
    return device is not None and device.get("device_type") == "cisco_xe"


def is_linux_device(device_name: str) -> bool:
    """Check if a device is a Linux host (including containerlab linux)."""
    device = DEVICES.get(device_name)
    if device is None:
        return False
    dtype = device.get("device_type", "")
    return dtype in ("linux", "containerlab_linux")


def is_containerlab_device(device_name: str) -> bool:
    """Check if a device is a containerlab container."""
    device = DEVICES.get(device_name)
    if device is None:
        return False
    return device.get("device_type", "").startswith("containerlab_")
