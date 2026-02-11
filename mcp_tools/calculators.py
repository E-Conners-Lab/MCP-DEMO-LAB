"""
Calculator MCP tools.

Pure calculation tools with no network dependencies:
- calculate_tunnel_mtu: Calculate optimal MTU/MSS for VPN tunnels
- get_mtu_scenarios: Pre-calculated MTU values for common scenarios
- calculate_subnet_info: Calculate subnet details from IP address
- split_network: Split network into smaller subnets (VLSM)
- get_subnet_reference: Reference table of common subnet sizes
- convert_netmask: Convert between CIDR prefix and dotted decimal
"""

# =============================================================================
# Subnet Calculator (inline — no external dependency)
# =============================================================================
import ipaddress
import json


async def calculate_subnet_info(address: str, netmask: str = None) -> str:
    """
    Calculate detailed subnet information from an IP address.

    Args:
        address: IP address in CIDR notation (e.g., "192.168.1.0/24")
                 or plain IP (e.g., "192.168.1.100")
        netmask: Optional netmask if not using CIDR notation
                 (e.g., "255.255.255.0")

    Returns:
        JSON with network address, broadcast, netmask, usable hosts, etc.

    Examples:
        calculate_subnet_info("192.168.1.0/24")
        calculate_subnet_info("10.0.12.1/30")
        calculate_subnet_info("192.168.1.100", "255.255.255.0")
    """
    try:
        if netmask and "/" not in address:
            # Convert dotted netmask to prefix length
            prefix = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
            address = f"{address}/{prefix}"

        network = ipaddress.ip_network(address, strict=False)

        result = {
            "network": str(network.network_address),
            "prefix_length": network.prefixlen,
            "netmask": str(network.netmask),
            "broadcast": str(network.broadcast_address) if network.version == 4 else "N/A",
            "first_usable": (
                str(network.network_address + 1) if network.num_addresses > 2
                else str(network.network_address)
            ),
            "last_usable": (
                str(network.broadcast_address - 1) if network.num_addresses > 2
                else str(network.broadcast_address)
            ),
            "total_addresses": network.num_addresses,
            "usable_hosts": (
                max(0, network.num_addresses - 2) if network.prefixlen < 31
                else network.num_addresses
            ),
            "wildcard_mask": str(network.hostmask) if network.version == 4 else "N/A",
            "ip_version": network.version,
            "is_private": network.is_private,
            "cidr": str(network),
        }

        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


async def split_network(network: str, new_prefix: int) -> str:
    """
    Split a network into smaller subnets (VLSM).

    Args:
        network: Network in CIDR notation (e.g., "192.168.1.0/24")
        new_prefix: New prefix length (must be larger than original)

    Returns:
        JSON with list of subnets

    Examples:
        split_network("192.168.1.0/24", 26)  # Four /26 subnets
        split_network("10.0.0.0/16", 24)     # 256 /24 subnets
    """
    try:
        net = ipaddress.ip_network(network, strict=False)
        subnets = list(net.subnets(new_prefix=new_prefix))

        result = {
            "original_network": str(net),
            "new_prefix": new_prefix,
            "subnet_count": len(subnets),
            "subnets": [
                {
                    "network": str(s),
                    "first_usable": (
                        str(s.network_address + 1) if s.num_addresses > 2
                        else str(s.network_address)
                    ),
                    "last_usable": (
                        str(s.broadcast_address - 1) if s.num_addresses > 2
                        else str(s.broadcast_address)
                    ),
                    "usable_hosts": max(0, s.num_addresses - 2),
                }
                for s in subnets[:256]  # Cap output for large splits
            ],
        }

        if len(subnets) > 256:
            result["note"] = f"Showing first 256 of {len(subnets)} subnets"

        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


async def get_subnet_reference() -> str:
    """
    Get a reference table of common subnet sizes.

    Returns:
        JSON with prefix lengths, netmasks, and usable hosts
    """
    subnets = []
    for prefix in range(32, 15, -1):
        net = ipaddress.IPv4Network(f"0.0.0.0/{prefix}")
        usable = max(0, net.num_addresses - 2) if prefix < 31 else net.num_addresses
        subnets.append({
            "prefix": f"/{prefix}",
            "netmask": str(net.netmask),
            "addresses": net.num_addresses,
            "usable_hosts": usable,
            "wildcard": str(net.hostmask),
        })

    return json.dumps({
        "common_subnets": subnets,
        "notes": {
            "/31": "Point-to-point links (RFC 3021) — both addresses usable",
            "/32": "Host routes — single address",
        }
    }, indent=2)


async def convert_netmask(value: str) -> str:
    """
    Convert between CIDR prefix and dotted decimal netmask.

    Args:
        value: Either a prefix length (e.g., "24") or netmask (e.g., "255.255.255.0")

    Returns:
        JSON with both CIDR prefix and dotted decimal netmask

    Examples:
        convert_netmask("24")              # /24 = 255.255.255.0
        convert_netmask("255.255.255.0")   # 255.255.255.0 = /24
    """
    try:
        if value.isdigit():
            prefix = int(value)
            if not 0 <= prefix <= 32:
                return json.dumps({"error": f"Prefix must be 0-32, got {prefix}"})
            net = ipaddress.IPv4Network(f"0.0.0.0/{prefix}")
            return json.dumps({
                "prefix_length": prefix,
                "netmask": str(net.netmask),
                "cidr": f"/{prefix}",
            }, indent=2)
        else:
            net = ipaddress.IPv4Network(f"0.0.0.0/{value}")
            return json.dumps({
                "netmask": value,
                "prefix_length": net.prefixlen,
                "cidr": f"/{net.prefixlen}",
            }, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


async def calculate_tunnel_mtu(
    tunnel_type: str,
    physical_mtu: int = 1500,
    encryption: str = None,
    nat_traversal: bool = False,
) -> str:
    """
    Calculate optimal tunnel MTU and TCP MSS for VPN tunnels.

    Prevents fragmentation by accounting for tunnel overhead.

    Args:
        tunnel_type: "gre", "gre_ipsec", "ipsec_tunnel", "vxlan", "wireguard"
        physical_mtu: Physical interface MTU (default: 1500)
        encryption: IPsec encryption: "aes-256-gcm", "aes-256-cbc", etc.
        nat_traversal: Whether NAT-T (UDP encap) is used

    Returns:
        JSON with calculated MTU, MSS, and overhead breakdown
    """
    # Overhead values in bytes
    overhead_map = {
        "gre": 24,                # IP(20) + GRE(4)
        "gre_ipsec": 73,          # IP(20) + GRE(4) + ESP(8+16+1) + AES-GCM(8+16)
        "ipsec_tunnel": 73,       # IP(20) + ESP(8+16+1) + IV(8) + AES-GCM(16) + padding
        "ipsec_transport": 53,    # ESP(8+16+1) + IV(8) + AES-GCM(16) + padding
        "vxlan": 54,              # Outer-IP(20) + UDP(8) + VXLAN(8) + Ethernet(18)
        "wireguard": 60,          # IP(20) + UDP(8) + WG(32)
    }

    tunnel = tunnel_type.lower()
    if tunnel not in overhead_map:
        return json.dumps({
            "error": f"Unknown tunnel type: {tunnel_type}",
            "valid_types": list(overhead_map.keys()),
        }, indent=2)

    overhead = overhead_map[tunnel]

    # NAT-T adds UDP encapsulation (8 bytes)
    if nat_traversal and tunnel in ("gre_ipsec", "ipsec_tunnel", "ipsec_transport"):
        overhead += 8

    # Encryption-specific adjustments
    if encryption and "cbc" in encryption.lower():
        overhead += 8  # CBC modes have larger padding requirements

    tunnel_mtu = physical_mtu - overhead
    tcp_mss = tunnel_mtu - 40  # TCP(20) + IP(20)

    return json.dumps({
        "tunnel_type": tunnel_type,
        "physical_mtu": physical_mtu,
        "overhead_bytes": overhead,
        "tunnel_mtu": tunnel_mtu,
        "tcp_mss": tcp_mss,
        "nat_traversal": nat_traversal,
        "recommendation": f"ip mtu {tunnel_mtu}",
        "mss_recommendation": f"ip tcp adjust-mss {tcp_mss}",
    }, indent=2)


async def get_mtu_scenarios() -> str:
    """
    Get pre-calculated MTU/MSS values for common tunnel scenarios.

    Returns recommended settings for DMVPN, site-to-site IPsec,
    pure GRE, VXLAN, and WireGuard.
    """
    scenarios = {
        "DMVPN (GRE+IPsec, AES-256-GCM)": {"overhead": 73, "mtu": 1427, "mss": 1387},
        "DMVPN with NAT-T": {"overhead": 81, "mtu": 1419, "mss": 1379},
        "Site-to-Site IPsec (AES-256-CBC)": {"overhead": 81, "mtu": 1419, "mss": 1379},
        "Pure GRE (no encryption)": {"overhead": 24, "mtu": 1476, "mss": 1436},
        "VXLAN": {"overhead": 54, "mtu": 1446, "mss": 1406},
        "WireGuard": {"overhead": 60, "mtu": 1440, "mss": 1400},
    }

    return json.dumps({
        "physical_mtu": 1500,
        "scenarios": scenarios,
        "note": "Use calculate_tunnel_mtu() for custom parameters",
    }, indent=2)


# =============================================================================
# Tool Registry
# =============================================================================

TOOLS = [
    {"fn": calculate_tunnel_mtu, "name": "calculate_tunnel_mtu", "category": "calculators"},
    {"fn": get_mtu_scenarios, "name": "get_mtu_scenarios", "category": "calculators"},
    {"fn": calculate_subnet_info, "name": "calculate_subnet_info", "category": "calculators"},
    {"fn": split_network, "name": "split_network", "category": "calculators"},
    {"fn": get_subnet_reference, "name": "get_subnet_reference", "category": "calculators"},
    {"fn": convert_netmask, "name": "convert_netmask", "category": "calculators"},
]
