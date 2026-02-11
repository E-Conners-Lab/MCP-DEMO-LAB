"""Unified CLI output parser.

Wraps ntc-templates and regex-based parsing to convert raw CLI output
into structured dicts.  Falls back to line-splitting when no parser is
available.
"""

import logging
import re

logger = logging.getLogger(__name__)


def parse_cli_output(command: str, raw_output: str, platform: str = "cisco_ios") -> list[dict]:
    """Parse raw CLI output into a list of dicts using ntc-templates.

    Falls back to simple line-based splitting if ntc-templates cannot
    parse the command.

    Args:
        command: The CLI command that produced the output
        raw_output: Raw text output from the device
        platform: NTC-templates platform name (default: ``cisco_ios``)

    Returns:
        List of dicts, one per parsed row/entry
    """
    try:
        from ntc_templates.parse import parse_output
        parsed = parse_output(platform=platform, command=command, data=raw_output)
        if parsed:
            return parsed
    except ImportError:
        logger.debug("ntc-templates not installed, falling back to regex parsing")
    except Exception as exc:
        logger.debug("ntc-templates parsing failed for '%s': %s", command, exc)

    # Fallback: return raw lines as list of dicts
    return _fallback_parse(raw_output)


def _fallback_parse(raw_output: str) -> list[dict]:
    """Simple fallback: split output into non-empty lines."""
    lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
    return [{"line": line} for line in lines]


def parse_show_ip_interface_brief(raw_output: str) -> list[dict]:
    """Parse ``show ip interface brief`` output.

    Returns list of dicts with keys: interface, ip_address, ok, method, status, protocol
    """
    results = []
    for line in raw_output.splitlines():
        # Match typical IOS output: Interface  IP  OK?  Method  Status  Protocol
        match = re.match(
            r'^(\S+)\s+'           # interface
            r'(\S+)\s+'            # ip_address
            r'(YES|NO)\s+'         # ok
            r'(\S+)\s+'            # method
            r'((?:administratively )?\S+)\s+'  # status
            r'(\S+)\s*$',          # protocol
            line,
        )
        if match:
            results.append({
                "interface": match.group(1),
                "ip_address": match.group(2),
                "ok": match.group(3),
                "method": match.group(4),
                "status": match.group(5),
                "protocol": match.group(6),
            })
    return results


def parse_show_ip_route(raw_output: str) -> list[dict]:
    """Parse ``show ip route`` output into structured routes.

    Handles connected (C), OSPF (O), static (S), BGP (B), and other codes.
    """
    results = []
    code_map = {
        "C": "connected", "L": "local", "S": "static",
        "O": "ospf", "B": "bgp", "D": "eigrp",
        "R": "rip", "i": "isis",
    }

    for line in raw_output.splitlines():
        # Match: CODE prefix [metric/distance] via next_hop, interface
        match = re.match(
            r'^\s*([CLOSBDR*i]+)\s+'  # route code(s)
            r'(\S+)\s+'               # prefix
            r'(?:\[(\d+)/(\d+)\]\s+'  # [distance/metric]
            r'via\s+(\S+))?'          # via next_hop
            r'(?:,\s*(\S+))?',        # interface
            line,
        )
        if match:
            code = match.group(1).strip("* ")
            protocol = code_map.get(code[0] if code else "", "unknown")
            entry = {
                "prefix": match.group(2),
                "protocol": protocol,
            }
            if match.group(3):
                entry["distance"] = int(match.group(3))
                entry["metric"] = int(match.group(4))
            if match.group(5):
                entry["next_hop"] = match.group(5).rstrip(",")
            else:
                entry["next_hop"] = "connected"
            if match.group(6):
                entry["interface"] = match.group(6)
            results.append(entry)

    return results
