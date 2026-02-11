"""Output normalization utilities.

Provides helpers to clean up and normalise CLI output from various
network device platforms into consistent formats.
"""

import re


def normalize_interface_name(name: str) -> str:
    """Normalize interface name abbreviations to full form.

    Examples:
        Gi0/1 → GigabitEthernet0/1
        Fa0/1 → FastEthernet0/1
        Te0/0/0 → TenGigabitEthernet0/0/0
        Lo0 → Loopback0
    """
    # Full names returned as-is (check long forms first)
    full_names = (
        'GigabitEthernet', 'FastEthernet', 'TenGigabitEthernet',
        'TwentyFiveGigE', 'FortyGigabitEthernet', 'HundredGigE',
        'Loopback', 'Vlan', 'Tunnel', 'Port-channel', 'Ethernet',
    )
    for full in full_names:
        if name.startswith(full):
            return name

    abbrev_map = [
        (r'^Gi(?:g)?', 'GigabitEthernet'),
        (r'^Fa', 'FastEthernet'),
        (r'^Te(?:n)?', 'TenGigabitEthernet'),
        (r'^Tw', 'TwentyFiveGigE'),
        (r'^Fo', 'FortyGigabitEthernet'),
        (r'^Hu', 'HundredGigE'),
        (r'^Lo', 'Loopback'),
        (r'^Vl', 'Vlan'),
        (r'^Tu', 'Tunnel'),
        (r'^Po', 'Port-channel'),
        (r'^Eth', 'Ethernet'),
    ]
    for pattern, replacement in abbrev_map:
        if re.match(pattern, name):
            return re.sub(pattern, replacement, name)
    return name


def normalize_mac_address(mac: str) -> str:
    """Normalize MAC address to colon-separated format (aa:bb:cc:dd:ee:ff).

    Handles Cisco (aabb.ccdd.eeff), dash (aa-bb-cc-dd-ee-ff),
    and colon (aa:bb:cc:dd:ee:ff) formats.
    """
    # Remove all separators
    raw = re.sub(r'[.:\-]', '', mac.lower())
    if len(raw) != 12:
        return mac  # Return as-is if not a valid MAC
    return ':'.join(raw[i:i+2] for i in range(0, 12, 2))


def normalize_speed(speed_str: str) -> str:
    """Normalize interface speed strings to Mbps.

    Examples:
        "1000Mbps" → "1000"
        "10Gbps" → "10000"
        "auto" → "auto"
    """
    if not speed_str or speed_str.lower() in ("auto", "unknown", ""):
        return "auto"

    match = re.match(r'(\d+)\s*(G|M|K)?', speed_str, re.IGNORECASE)
    if not match:
        return speed_str

    value = int(match.group(1))
    unit = (match.group(2) or 'M').upper()

    multipliers = {'K': 0.001, 'M': 1, 'G': 1000}
    return str(int(value * multipliers.get(unit, 1)))


def clean_output(raw: str) -> str:
    """Remove ANSI escape codes and trailing whitespace from CLI output."""
    # Strip ANSI escape sequences
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw)
    # Normalize line endings and strip trailing whitespace
    lines = [line.rstrip() for line in cleaned.splitlines()]
    return '\n'.join(lines).strip()
