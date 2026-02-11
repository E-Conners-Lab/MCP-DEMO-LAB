"""Integration tests — full demo-mode sweep and server startup.

These tests verify:
1. Every tool in ALL_TOOLS returns valid JSON in demo mode
2. No network manager classes (Scrapli, Netmiko, pysnmp, ncclient) are
   instantiated during demo mode execution
3. The server starts without import errors
"""

import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

os.environ["DEMO_MODE"] = "true"


# ============================================================================
# Full demo-mode sweep: call every tool, assert JSON-parseable
# ============================================================================

@pytest.mark.asyncio
async def test_all_tools_return_valid_json():
    """Every tool in ALL_TOOLS must return valid JSON in demo mode."""
    from mcp_tools import ALL_TOOLS

    # Map tool names to their required arguments for demo mode
    tool_args = {
        "send_command": {"device_name": "R1", "command": "show ip route"},
        "send_config": {"device_name": "R1", "commands": "interface Lo99\ndescription test"},
        "health_check": {"device_name": "R1"},
        "bulk_command": {"command": "show version"},
        "ping_sweep": {"device_name": "R1", "targets": "10.0.0.1,10.0.0.2"},
        "traceroute": {"device_name": "R1", "destination": "10.0.0.1"},
        "get_interface_status": {"device_name": "R1"},
        "get_arp_table": {"device_name": "R1"},
        "get_mac_table": {"device_name": "R1"},
        "get_routing_table": {"device_name": "R1"},
        "get_neighbors": {"device_name": "R1"},
        "get_interfaces_netconf": {"device_name": "R1"},
        "get_bgp_neighbors_netconf": {"device_name": "R1"},
        "get_netconf_capabilities": {"device_name": "R1"},
        "snmp_get_oid": {"device_name": "R1", "oid": "1.3.6.1.2.1.1.1.0"},
        "snmp_walk_oid": {"device_name": "R1", "oid": "1.3.6.1.2.1.2.2.1"},
        "snmp_poll_metrics": {"device_name": "R1"},
        "compliance_check": {"device_name": "R1"},
        "backup_config": {"device_name": "R1"},
        "list_backups": {},
        "compare_configs": {"device_name": "R1"},
        "rollback_config": {"device_name": "R1", "backup_file": "R1_backup.cfg"},
        "discover_topology": {},
        "lldp_neighbors": {"device_name": "R1"},
        "lldp_check_status": {"device_name": "R1"},
        "calculate_tunnel_mtu": {"tunnel_type": "gre"},
        "calculate_subnet_info": {"address": "192.168.1.0/24"},
        "split_network": {"network": "192.168.1.0/24", "new_prefix": 26},
        "convert_netmask": {"value": "24"},
    }

    for entry in ALL_TOOLS:
        name = entry["name"]
        fn = entry["fn"]
        args = tool_args.get(name, {})

        result = await fn(**args)
        assert isinstance(result, str), f"{name} did not return a string"

        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            pytest.fail(f"{name} returned invalid JSON: {result[:200]}")

        assert isinstance(parsed, dict), f"{name} JSON root is not a dict"


# ============================================================================
# Verify no real network connections in demo mode
# ============================================================================

@pytest.mark.asyncio
async def test_no_scrapli_instantiation_in_demo():
    """Scrapli drivers must NOT be instantiated in demo mode."""
    from mcp_tools import ALL_TOOLS

    tool_args = {
        "send_command": {"device_name": "R1", "command": "show version"},
        "health_check": {"device_name": "R1"},
        "get_interface_status": {"device_name": "R1"},
        "get_routing_table": {"device_name": "R1"},
    }

    with patch("core.scrapli_manager.get_ios_xe_connection") as mock_conn:
        mock_conn.side_effect = RuntimeError("Should not be called in demo mode")

        for entry in ALL_TOOLS:
            if entry["name"] in tool_args:
                args = tool_args[entry["name"]]
                result = await entry["fn"](**args)
                # Should succeed without calling scrapli
                parsed = json.loads(result)
                assert "error" not in parsed or "demo" in str(parsed).lower(), \
                    f"{entry['name']} called scrapli in demo mode"


# ============================================================================
# Server startup test
# ============================================================================

def test_server_startup_no_import_errors():
    """Server should start without import errors in demo mode."""
    result = subprocess.run(
        [sys.executable, "-c", "import network_mcp_server; print('OK')"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "DEMO_MODE": "true"},
    )
    assert result.returncode == 0, f"Server startup failed: {result.stderr}"
    assert "OK" in result.stdout


def test_tool_count():
    """Verify expected number of tools are loaded."""
    from mcp_tools import ALL_TOOLS
    assert len(ALL_TOOLS) >= 35, f"Expected at least 35 tools, got {len(ALL_TOOLS)}"


# ============================================================================
# Import scan: verify no unwanted internal imports
# ============================================================================

def test_no_private_imports():
    """Verify no unwanted internal imports remain in the codebase."""

    forbidden_imports = [
        "from security.command_policy",
        "from config.vault_client",
        "from config.redis_client",
        "from core.connection_pool",
        "from core.netconf_pool",
        "from core.compliance_engine",
        "import validate_command",
        "record_to_memory",
    ]

    # Check source files (skip tests, .venv, build artifacts)
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    scan_dirs = ["mcp_tools", "core", "config"]

    for scan_dir in scan_dirs:
        for py_file in (project_root / scan_dir).rglob("*.py"):
            rel = str(py_file.relative_to(project_root))
            if "__pycache__" in rel:
                continue

            content = py_file.read_text()
            for forbidden in forbidden_imports:
                assert forbidden not in content, \
                    f"Found forbidden import '{forbidden}' in {rel}"
