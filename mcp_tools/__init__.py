"""
MCP Tools Registry

Unified registry for all MCP tools with duplicate name detection.

Usage:
    from mcp_tools import ALL_TOOLS

    for entry in ALL_TOOLS:
        mcp.tool()(entry["fn"])
"""

from typing import Any, Callable, Dict, List

from .calculators import TOOLS as calculators_tools
from .compliance import TOOLS as compliance_tools
from .config import TOOLS as config_tools

# Import tool modules
from .device import TOOLS as device_tools
from .interfaces import TOOLS as interfaces_tools
from .netconf import TOOLS as netconf_tools
from .operations import TOOLS as operations_tools
from .routing import TOOLS as routing_tools
from .snmp import TOOLS as snmp_tools
from .topology import TOOLS as topology_tools


def _build_registry(*tool_lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build the ALL_TOOLS registry with uniqueness checking."""
    all_tools = []
    seen_names = set()

    for tool_list in tool_lists:
        for entry in tool_list:
            name = entry["name"]
            if name in seen_names:
                raise ValueError(f"Duplicate tool name detected: {name}")
            seen_names.add(name)
            all_tools.append(entry)

    return all_tools


ALL_TOOLS = _build_registry(
    device_tools,
    calculators_tools,
    topology_tools,
    config_tools,
    operations_tools,
    interfaces_tools,
    routing_tools,
    netconf_tools,
    snmp_tools,
    compliance_tools,
)


def get_tool_functions() -> List[Callable]:
    """Return list of tool functions for MCP registration."""
    return [entry["fn"] for entry in ALL_TOOLS]


def get_tool_by_name(name: str) -> Dict[str, Any] | None:
    """Get a specific tool by name."""
    for t in ALL_TOOLS:
        if t["name"] == name:
            return t
    return None


def get_categories() -> List[str]:
    """Return list of all unique categories."""
    return list(set(t["category"] for t in ALL_TOOLS))


__all__ = ["ALL_TOOLS", "get_tool_functions", "get_tool_by_name", "get_categories"]
