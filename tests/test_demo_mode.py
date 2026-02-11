"""Tests for demo mode — all tools should return mock data without devices."""

import json
import os

import pytest

# Ensure demo mode is on
os.environ["DEMO_MODE"] = "true"

from mcp_tools.compliance import compliance_check, full_network_test
from mcp_tools.config import backup_config, list_backups
from mcp_tools.device import get_devices, health_check, health_check_all, send_command
from mcp_tools.interfaces import get_arp_table, get_interface_status
from mcp_tools.netconf import get_interfaces_netconf
from mcp_tools.operations import bulk_command, ping_sweep, traceroute
from mcp_tools.routing import get_neighbors, get_routing_table
from mcp_tools.snmp import snmp_get_oid, snmp_poll_metrics
from mcp_tools.topology import discover_topology


@pytest.mark.asyncio
async def test_get_devices_demo():
    result = json.loads(await get_devices())
    assert "devices" in result
    assert result["count"] > 0
    assert "R1" in result["devices"]


@pytest.mark.asyncio
async def test_health_check_demo():
    result = json.loads(await health_check("R1"))
    assert result["device"] == "R1"
    assert result["status"] == "healthy"
    assert "cpu_usage" in result


@pytest.mark.asyncio
async def test_health_check_all_demo():
    result = json.loads(await health_check_all())
    assert "summary" in result
    assert result["summary"]["total"] > 0


@pytest.mark.asyncio
async def test_send_command_demo():
    result = json.loads(await send_command("R1", "show ip route"))
    assert result["device"] == "R1"
    assert "DEMO" in result["output"]


@pytest.mark.asyncio
async def test_discover_topology_demo():
    result = json.loads(await discover_topology())
    assert "nodes" in result
    assert "edges" in result


@pytest.mark.asyncio
async def test_backup_config_demo():
    result = json.loads(await backup_config("R1"))
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_list_backups_demo():
    result = json.loads(await list_backups())
    assert "backups" in result


@pytest.mark.asyncio
async def test_bulk_command_demo():
    result = json.loads(await bulk_command("show version"))
    assert "results" in result
    assert result["summary"]["total"] > 0


@pytest.mark.asyncio
async def test_routing_table_demo():
    result = json.loads(await get_routing_table("R1"))
    assert "routes" in result


@pytest.mark.asyncio
async def test_neighbors_demo():
    result = json.loads(await get_neighbors("R1"))
    assert "ospf_neighbors" in result


@pytest.mark.asyncio
async def test_interface_status_demo():
    result = json.loads(await get_interface_status("R1"))
    assert "interfaces" in result


@pytest.mark.asyncio
async def test_arp_table_demo():
    result = json.loads(await get_arp_table("R1"))
    assert "entries" in result


@pytest.mark.asyncio
async def test_snmp_get_demo():
    result = json.loads(await snmp_get_oid("R1", "1.3.6.1.2.1.1.1.0"))
    assert "value" in result


@pytest.mark.asyncio
async def test_snmp_poll_demo():
    result = json.loads(await snmp_poll_metrics("R1"))
    assert "cpu_usage_percent" in result


@pytest.mark.asyncio
async def test_netconf_interfaces_demo():
    result = json.loads(await get_interfaces_netconf("R1"))
    assert "interfaces" in result


@pytest.mark.asyncio
async def test_ping_sweep_demo():
    result = json.loads(await ping_sweep("R1", "10.0.12.2,10.0.23.2,10.0.34.2"))
    assert "reachable" in result
    assert "unreachable" in result
    assert result["summary"]["total"] == 3


@pytest.mark.asyncio
async def test_traceroute_demo():
    result = json.loads(await traceroute("R1", "198.51.100.3"))
    assert result["destination"] == "198.51.100.3"
    assert len(result["hops"]) > 0


@pytest.mark.asyncio
async def test_compliance_check_demo():
    result = json.loads(await compliance_check("R1"))
    assert result["status"] == "pass"


@pytest.mark.asyncio
async def test_full_network_test_demo():
    result = json.loads(await full_network_test())
    assert result["status"] == "pass"
    assert result["summary"]["total_devices"] > 0
