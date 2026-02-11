"""
MCP Server for Network Automation

Gives AI assistants direct access to network devices via the
Model Context Protocol (MCP). Supports Cisco IOS-XE, Nokia SR Linux,
FRRouting, Juniper Junos, Aruba AOS-CX, and Linux hosts.

Usage:
    # With real devices
    python network_mcp_server.py

    # Demo mode (no devices needed)
    DEMO_MODE=true python network_mcp_server.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_tools import ALL_TOOLS  # noqa: E402

# Create the MCP server instance
mcp = FastMCP("network-mcp")

# Register all tools
for _entry in ALL_TOOLS:
    mcp.tool()(_entry["fn"])


def main():
    """Entry point for the MCP server."""
    demo = os.getenv("DEMO_MODE", "false").lower() == "true"
    if demo:
        print("Starting network-mcp in DEMO MODE (mock data, no real devices)")
    else:
        print("Starting network-mcp server")
    mcp.run()


if __name__ == "__main__":
    main()
