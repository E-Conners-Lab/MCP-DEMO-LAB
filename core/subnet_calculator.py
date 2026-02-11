"""Subnet calculation engine.

Pure-Python subnet math using the standard library ``ipaddress`` module.
"""

import ipaddress


def calculate_subnet(address: str, netmask: str | None = None) -> dict:
    """Calculate subnet details from a CIDR address or IP+netmask pair.

    Args:
        address: CIDR notation (``192.168.1.0/24``) or bare IP
        netmask: Optional dotted-decimal netmask (``255.255.255.0``)

    Returns:
        Dict with network, prefix_length, netmask, broadcast, usable range, etc.
    """
    try:
        if netmask:
            prefix = ipaddress.ip_network(f"{address}/{netmask}", strict=False)
        else:
            prefix = ipaddress.ip_network(address, strict=False)
    except ValueError as exc:
        return {"error": str(exc)}

    total = prefix.num_addresses
    if prefix.prefixlen == 32:
        usable = 1
        first = last = str(prefix.network_address)
    elif prefix.prefixlen == 31:
        usable = 2
        first = str(prefix.network_address)
        last = str(prefix.broadcast_address)
    else:
        usable = total - 2
        first = str(prefix.network_address + 1)
        last = str(prefix.broadcast_address - 1)

    wildcard = ipaddress.IPv4Address(int(prefix.hostmask))

    return {
        "network": str(prefix.network_address),
        "prefix_length": prefix.prefixlen,
        "netmask": str(prefix.netmask),
        "broadcast": str(prefix.broadcast_address),
        "first_usable": first,
        "last_usable": last,
        "total_addresses": total,
        "usable_hosts": usable,
        "wildcard_mask": str(wildcard),
        "is_private": prefix.is_private,
        "cidr": str(prefix),
    }


def split_network(network: str, new_prefix: int) -> dict:
    """Split a network into subnets with a given prefix length.

    Args:
        network: CIDR notation of the parent network
        new_prefix: Target prefix length for subnets

    Returns:
        Dict with original_network, new_prefix, subnet_count, and subnets list
    """
    try:
        parent = ipaddress.ip_network(network, strict=False)
    except ValueError as exc:
        return {"error": str(exc)}

    if new_prefix <= parent.prefixlen:
        return {"error": f"New prefix /{new_prefix} must be longer than /{parent.prefixlen}"}

    subnets = list(parent.subnets(new_prefix=new_prefix))

    # Cap output to prevent huge responses
    MAX_DISPLAY = 256
    display = subnets[:MAX_DISPLAY]

    result_list = []
    for subnet in display:
        usable = max(0, subnet.num_addresses - 2) if subnet.prefixlen < 31 else subnet.num_addresses
        result_list.append({
            "network": str(subnet),
            "first_usable": (
                str(subnet.network_address + 1) if subnet.prefixlen < 31
                else str(subnet.network_address)
            ),
            "last_usable": (
                str(subnet.broadcast_address - 1) if subnet.prefixlen < 31
                else str(subnet.broadcast_address)
            ),
            "broadcast": str(subnet.broadcast_address),
            "usable_hosts": usable,
        })

    return {
        "original_network": str(parent),
        "new_prefix": new_prefix,
        "subnet_count": len(subnets),
        "subnets": result_list,
    }
