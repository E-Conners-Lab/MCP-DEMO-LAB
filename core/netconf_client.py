"""NETCONF client for YANG-based device interaction.

Uses ncclient with ``asyncio.to_thread`` to provide async-friendly
NETCONF operations.  Each call opens a fresh connection (no pooling).
"""

import asyncio
import logging

from config.devices import DEVICES, PASSWORD, USERNAME

logger = logging.getLogger(__name__)

NETCONF_PORT = 830


def _get_netconf_params(device_name: str) -> dict:
    """Build ncclient connection parameters for a device."""
    device = DEVICES.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in inventory")

    return {
        "host": device.get("host", ""),
        "port": device.get("netconf_port", NETCONF_PORT),
        "username": device.get("username", USERNAME),
        "password": device.get("password", PASSWORD),
        "hostkey_verify": False,
        "device_params": {"name": "iosxe"},
    }


async def get_config(device_name: str, source: str = "running", filter_xml: str = None) -> str:
    """Retrieve configuration via NETCONF <get-config>.

    Returns the XML response as a string.
    """
    from ncclient import manager

    params = _get_netconf_params(device_name)

    def _run():
        with manager.connect(**params) as m:
            if filter_xml:
                result = m.get_config(source=source, filter=("subtree", filter_xml))
            else:
                result = m.get_config(source=source)
            return result.xml

    return await asyncio.to_thread(_run)


async def get_operational(device_name: str, filter_xml: str) -> str:
    """Retrieve operational data via NETCONF <get>.

    Returns the XML response as a string.
    """
    from ncclient import manager

    params = _get_netconf_params(device_name)

    def _run():
        with manager.connect(**params) as m:
            result = m.get(filter=("subtree", filter_xml))
            return result.xml

    return await asyncio.to_thread(_run)


async def edit_config(device_name: str, config_xml: str, target: str = "running") -> str:
    """Apply configuration via NETCONF <edit-config>.

    Returns the XML response as a string.
    """
    from ncclient import manager

    params = _get_netconf_params(device_name)

    def _run():
        with manager.connect(**params) as m:
            result = m.edit_config(target=target, config=config_xml)
            return result.xml

    return await asyncio.to_thread(_run)


async def get_capabilities(device_name: str) -> list[str]:
    """Return the list of NETCONF capabilities advertised by the device."""
    from ncclient import manager

    params = _get_netconf_params(device_name)

    def _run():
        with manager.connect(**params) as m:
            return list(m.server_capabilities)

    return await asyncio.to_thread(_run)
