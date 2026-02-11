"""Tests for calculator MCP tools."""

import json

import pytest

from mcp_tools.calculators import (
    calculate_subnet_info,
    calculate_tunnel_mtu,
    convert_netmask,
    get_mtu_scenarios,
    get_subnet_reference,
    split_network,
)


@pytest.mark.asyncio
async def test_calculate_subnet_info_cidr():
    result = json.loads(await calculate_subnet_info("192.168.1.0/24"))
    assert result["network"] == "192.168.1.0"
    assert result["prefix_length"] == 24
    assert result["netmask"] == "255.255.255.0"
    assert result["usable_hosts"] == 254
    assert result["broadcast"] == "192.168.1.255"


@pytest.mark.asyncio
async def test_calculate_subnet_info_with_netmask():
    result = json.loads(await calculate_subnet_info("10.0.0.1", "255.255.255.252"))
    assert result["prefix_length"] == 30
    assert result["usable_hosts"] == 2


@pytest.mark.asyncio
async def test_calculate_subnet_info_point_to_point():
    result = json.loads(await calculate_subnet_info("10.0.12.1/30"))
    assert result["usable_hosts"] == 2
    assert result["first_usable"] == "10.0.12.1"
    assert result["last_usable"] == "10.0.12.2"


@pytest.mark.asyncio
async def test_calculate_subnet_info_invalid():
    result = json.loads(await calculate_subnet_info("not-an-ip"))
    assert "error" in result


@pytest.mark.asyncio
async def test_split_network():
    result = json.loads(await split_network("192.168.1.0/24", 26))
    assert result["subnet_count"] == 4
    assert len(result["subnets"]) == 4
    assert result["subnets"][0]["network"] == "192.168.1.0/26"


@pytest.mark.asyncio
async def test_convert_netmask_from_prefix():
    result = json.loads(await convert_netmask("24"))
    assert result["netmask"] == "255.255.255.0"
    assert result["prefix_length"] == 24


@pytest.mark.asyncio
async def test_convert_netmask_from_dotted():
    result = json.loads(await convert_netmask("255.255.255.0"))
    assert result["prefix_length"] == 24


@pytest.mark.asyncio
async def test_tunnel_mtu_gre():
    result = json.loads(await calculate_tunnel_mtu("gre"))
    assert result["tunnel_mtu"] == 1476  # 1500 - 24
    assert result["tcp_mss"] == 1436


@pytest.mark.asyncio
async def test_tunnel_mtu_gre_ipsec():
    result = json.loads(await calculate_tunnel_mtu("gre_ipsec"))
    assert result["tunnel_mtu"] == 1427  # 1500 - 73
    assert result["overhead_bytes"] == 73


@pytest.mark.asyncio
async def test_tunnel_mtu_invalid():
    result = json.loads(await calculate_tunnel_mtu("invalid_type"))
    assert "error" in result
    assert "valid_types" in result


@pytest.mark.asyncio
async def test_mtu_scenarios():
    result = json.loads(await get_mtu_scenarios())
    assert "scenarios" in result
    assert result["physical_mtu"] == 1500


@pytest.mark.asyncio
async def test_subnet_reference():
    result = json.loads(await get_subnet_reference())
    assert "common_subnets" in result
    assert len(result["common_subnets"]) > 0
