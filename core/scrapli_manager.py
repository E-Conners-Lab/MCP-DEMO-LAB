"""Scrapli connection manager for IOS-XE and Linux devices.

Provides simplified async connection helpers for sending show commands
and configuration to Cisco IOS-XE devices and Linux hosts via Scrapli.

No connection pooling — each call opens and closes a connection.
"""

import logging

from config.devices import get_scrapli_device

logger = logging.getLogger(__name__)


async def get_ios_xe_connection(device_name: str):
    """Return an open ``AsyncScrapli`` connection for a Cisco IOS-XE device.

    The caller is responsible for closing the connection (prefer ``async with``
    or an explicit ``conn.close()``).
    """
    from scrapli.driver.core import AsyncIOSXEDriver

    device = get_scrapli_device(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")

    conn = AsyncIOSXEDriver(
        host=device["host"],
        auth_username=device["auth_username"],
        auth_password=device["auth_password"],
        auth_strict_key=device["auth_strict_key"],
        transport="asyncssh",
    )
    await conn.open()
    return conn


async def get_linux_connection(device_name: str):
    """Return an open ``AsyncGenericDriver`` connection for a Linux host."""
    from scrapli.driver import AsyncGenericDriver

    device = get_scrapli_device(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")

    conn = AsyncGenericDriver(
        host=device["host"],
        auth_username=device["auth_username"],
        auth_password=device["auth_password"],
        auth_strict_key=device["auth_strict_key"],
        transport="asyncssh",
    )
    await conn.open()
    return conn


async def send_command(device_name: str, command: str, *, device_type: str = "cisco_xe") -> str:
    """Send a single show command and return its output as a string.

    Opens a connection, sends the command, closes the connection.
    """
    if device_type in ("linux", "containerlab_linux"):
        conn = await get_linux_connection(device_name)
    else:
        conn = await get_ios_xe_connection(device_name)

    try:
        response = await conn.send_command(command)
        return response.result
    finally:
        conn.close()


async def send_config(device_name: str, commands: list[str]) -> str:
    """Send configuration commands to an IOS-XE device.

    Returns the device's response text.
    """
    conn = await get_ios_xe_connection(device_name)
    try:
        response = await conn.send_configs(commands)
        return response.result
    finally:
        conn.close()
