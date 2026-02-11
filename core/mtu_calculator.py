"""MTU/MSS calculation engine.

Computes optimal tunnel MTU and TCP MSS values based on encapsulation
type, encryption overhead, and NAT traversal requirements.
"""

# Overhead in bytes per tunnel type
TUNNEL_OVERHEAD = {
    "gre": 24,
    "gre_ipsec": 73,
    "ipsec_tunnel": 73,
    "ipsec_transport": 53,
    "vxlan": 54,
    "wireguard": 60,
}

# Additional overhead adjustments
CBC_OVERHEAD = 8    # AES-CBC padding
NAT_T_OVERHEAD = 8  # NAT-Traversal UDP encapsulation
TCP_HEADER = 40     # IP (20) + TCP (20) header for MSS calculation


def calculate_mtu(
    tunnel_type: str,
    physical_mtu: int = 1500,
    encryption: str | None = None,
    nat_traversal: bool = False,
) -> dict:
    """Calculate optimal tunnel MTU and TCP MSS.

    Args:
        tunnel_type: One of the keys in ``TUNNEL_OVERHEAD``
        physical_mtu: Underlying link MTU (default 1500)
        encryption: Encryption type (``"aes-256-cbc"`` adds padding overhead)
        nat_traversal: Whether NAT-T is in use (adds 8 bytes)

    Returns:
        Dict with tunnel_mtu, tcp_mss, overhead_bytes, and recommendations
    """
    if tunnel_type not in TUNNEL_OVERHEAD:
        return {
            "error": f"Unknown tunnel type: {tunnel_type}",
            "valid_types": list(TUNNEL_OVERHEAD.keys()),
        }

    overhead = TUNNEL_OVERHEAD[tunnel_type]

    if encryption and "cbc" in encryption.lower():
        overhead += CBC_OVERHEAD
    if nat_traversal:
        overhead += NAT_T_OVERHEAD

    tunnel_mtu = physical_mtu - overhead
    tcp_mss = tunnel_mtu - TCP_HEADER

    recommendations = []
    if tunnel_mtu < 1400:
        recommendations.append("Consider increasing physical MTU if supported")
    if nat_traversal:
        recommendations.append("NAT-T adds 8 bytes — verify with actual traffic")

    return {
        "tunnel_type": tunnel_type,
        "physical_mtu": physical_mtu,
        "overhead_bytes": overhead,
        "tunnel_mtu": tunnel_mtu,
        "tcp_mss": tcp_mss,
        "encryption": encryption,
        "nat_traversal": nat_traversal,
        "recommendations": recommendations,
    }


def get_common_scenarios(physical_mtu: int = 1500) -> list[dict]:
    """Return pre-calculated MTU/MSS for common deployment scenarios."""
    scenarios = [
        ("DMVPN (GRE+IPsec, AES-256-GCM)", "gre_ipsec", None, False),
        ("DMVPN with NAT-T", "gre_ipsec", "aes-256-cbc", True),
        ("Site-to-Site IPsec (AES-256-CBC)", "ipsec_tunnel", "aes-256-cbc", False),
        ("Pure GRE", "gre", None, False),
        ("VXLAN", "vxlan", None, False),
        ("WireGuard", "wireguard", None, False),
    ]

    results = []
    for name, ttype, enc, nat in scenarios:
        calc = calculate_mtu(ttype, physical_mtu, enc, nat)
        results.append({
            "scenario": name,
            "tunnel_mtu": calc["tunnel_mtu"],
            "tcp_mss": calc["tcp_mss"],
            "overhead": calc["overhead_bytes"],
        })
    return results
