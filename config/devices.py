"""
Device inventory configuration.

Defines your network devices and credentials. All values can be
overridden via environment variables or .env file.

To add a device, add an entry to _STATIC_DEVICES with:
- device_type: One of the SUPPORTED_DEVICE_TYPES
- host: Management IP address
- username/password: SSH credentials
"""

import os

from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Credentials
# =============================================================================

USERNAME = os.getenv("DEVICE_USERNAME", "admin")
PASSWORD = os.getenv("DEVICE_PASSWORD", "admin")

# Containerlab VM name (if using Multipass)
CONTAINERLAB_VM = os.getenv("CONTAINERLAB_VM", "containerlab")

# SSH host key verification (disabled by default for lab use)
SSH_STRICT_KEY = os.getenv("SSH_STRICT_KEY", "false").lower() == "true"

# =============================================================================
# Supported Device Types
# =============================================================================

SUPPORTED_DEVICE_TYPES = [
    "cisco_xe",              # Cisco IOS-XE (routers, switches)
    "linux",                 # Linux hosts
    "juniper_junos",         # Juniper Junos
    "aruba_aoscx",           # HPE Aruba CX
    "containerlab_srlinux",  # Nokia SR Linux (containerlab)
    "containerlab_frr",      # FRRouting (containerlab)
    "containerlab_linux",    # Alpine Linux (containerlab)
]

# =============================================================================
# Device Inventory
# =============================================================================
# Add your own devices here. Override IPs via environment variables.
#
# Example: To override R1's IP, set R1_HOST=192.168.1.100 in .env

_STATIC_DEVICES = {
    # --- Example Cisco IOS-XE devices ---
    # Uncomment and modify for your lab:
    #
    # "R1": {
    #     "device_type": "cisco_xe",
    #     "host": os.getenv("R1_HOST", "10.255.255.11"),
    #     "username": USERNAME,
    #     "password": PASSWORD,
    # },
    # "R2": {
    #     "device_type": "cisco_xe",
    #     "host": os.getenv("R2_HOST", "10.255.255.12"),
    #     "username": USERNAME,
    #     "password": PASSWORD,
    # },

    # --- Example Containerlab devices ---
    # These work with the quickstart lab (quickstart/topology.clab.yml):
    #
    # "router1": {
    #     "device_type": "containerlab_frr",
    #     "container": "clab-quickstart-router1",
    #     "host": "172.20.20.11",
    # },
    # "router2": {
    #     "device_type": "containerlab_frr",
    #     "container": "clab-quickstart-router2",
    #     "host": "172.20.20.12",
    # },
}

# Device host lookup (name -> IP)
_STATIC_DEVICE_HOSTS = {
    name: device.get("host", "")
    for name, device in _STATIC_DEVICES.items()
}

# =============================================================================
# Active inventory (start with static, can be overridden by NetBox)
# =============================================================================

DEVICES = _STATIC_DEVICES
DEVICE_HOSTS = _STATIC_DEVICE_HOSTS


# =============================================================================
# Helper Functions
# =============================================================================

def get_device(name: str) -> dict | None:
    """Get a device by name."""
    return DEVICES.get(name)


def get_devices_by_type(device_type: str) -> dict:
    """Get all devices of a specific type."""
    return {
        name: device
        for name, device in DEVICES.items()
        if device.get("device_type") == device_type
    }


def is_containerlab_device(name: str) -> bool:
    """Check if device is a containerlab device."""
    device = DEVICES.get(name)
    if device is None:
        return False
    return device.get("device_type", "").startswith("containerlab_")


def is_cisco_device(name: str) -> bool:
    """Check if device is a Cisco IOS-XE device."""
    device = DEVICES.get(name)
    return device is not None and device.get("device_type") == "cisco_xe"


def is_linux_device(name: str) -> bool:
    """Check if device is a Linux host."""
    device = DEVICES.get(name)
    if device is None:
        return False
    dtype = device.get("device_type", "")
    return dtype == "linux" or dtype == "containerlab_linux"


def get_scrapli_device(name: str) -> dict | None:
    """Build a Scrapli connection dict for a device.

    Returns a dict suitable for passing to ``AsyncScrapli`` or
    ``scrapli_manager.get_ios_xe_connection``.  Credentials come from
    the ``DEVICE_USERNAME`` / ``DEVICE_PASSWORD`` env vars (no Vault).

    Returns ``None`` if the device is not in inventory.
    """
    device = DEVICES.get(name)
    if device is None:
        return None

    host = device.get("host", "")
    platform = device.get("device_type", "cisco_xe")

    # Map our device_type labels to Scrapli platform strings
    platform_map = {
        "cisco_xe": "cisco_iosxe",
        "juniper_junos": "juniper_junos",
        "aruba_aoscx": "aruba_aoscx",
    }
    scrapli_platform = platform_map.get(platform, "cisco_iosxe")

    return {
        "host": host,
        "auth_username": USERNAME,
        "auth_password": PASSWORD,
        "auth_strict_key": SSH_STRICT_KEY,
        "platform": scrapli_platform,
        "transport": "asyncssh",
    }
