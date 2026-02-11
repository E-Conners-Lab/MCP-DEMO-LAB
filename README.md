# network-mcp

**Give AI direct access to your network devices.** 35 MCP tools, multi-vendor, one interface.

Stop writing Netmiko scripts. Connect Claude, ChatGPT, or any MCP-compatible AI to your routers, switches, and firewalls — and let it run show commands, check health, calculate subnets, discover topology, and manage configs through natural language.

```
You: "Check the health of all my devices"
Claude: [calls health_check_all] → 6 devices healthy, Switch-R2 has 2 interfaces down
```

## What is this?

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that gives AI assistants real-time access to network devices. Built for network engineers who want to automate without writing boilerplate.

**Supported platforms:**
- Cisco IOS-XE (routers, switches)
- Nokia SR Linux
- FRRouting (FRR)
- Juniper Junos
- Aruba AOS-CX
- Linux hosts

## Quick Start

### 1. Install

```bash
git clone https://github.com/econners/network-mcp.git
cd network-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure devices

```bash
cp .env.example .env
# Edit .env with your device IPs and credentials
```

### 3. Try it instantly (no lab required)

```bash
# Demo mode returns realistic mock data — no devices needed
DEMO_MODE=true python network_mcp_server.py
```

### 4. Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "network": {
      "command": "/path/to/network-mcp/.venv/bin/python",
      "args": ["/path/to/network-mcp/network_mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. You now have 35 network tools available.

### 5. Try with a real lab (5 minutes)

```bash
# Spin up 2 FRR routers with containerlab
cd quickstart && sudo containerlab deploy -t topology.clab.yml
```

## Tools

### Device Operations
| Tool | Description |
|------|-------------|
| `get_devices` | List all devices in inventory |
| `send_command` | Run show commands on any device |
| `send_config` | Push configuration changes |
| `health_check` | Check device health (CPU, memory, interfaces) |
| `health_check_all` | Health check all devices in parallel |
| `backup_config` | Backup running configuration |
| `compare_configs` | Diff two config backups |
| `rollback_config` | Restore a previous config |

### Network Intelligence
| Tool | Description |
|------|-------------|
| `discover_topology` | LLDP-based topology discovery |
| `get_routing_table` | View routing tables |
| `get_neighbors` | BGP/OSPF neighbor status |
| `get_arp_table` | ARP table lookup |
| `get_mac_table` | MAC address table |
| `ping_sweep` | Sweep a subnet for reachable hosts |
| `traceroute` | Trace path to destination |

### Calculators (no devices needed)
| Tool | Description |
|------|-------------|
| `calculate_tunnel_mtu` | Optimal MTU/MSS for VPN tunnels |
| `calculate_subnet_info` | Subnet details from CIDR notation |
| `split_network` | VLSM subnet splitting |
| `convert_netmask` | CIDR to dotted decimal conversion |

### SNMP & Monitoring
| Tool | Description |
|------|-------------|
| `snmp_get_oid` | SNMP GET for specific OIDs |
| `snmp_walk_oid` | SNMP WALK subtrees |
| `snmp_poll_metrics` | Poll interface/CPU/memory metrics |

### NETCONF
| Tool | Description |
|------|-------------|
| `get_interfaces_netconf` | Interface data via NETCONF |
| `get_bgp_neighbors_netconf` | BGP state via NETCONF |
| `get_netconf_capabilities` | Device NETCONF capabilities |

### Configuration Management
| Tool | Description |
|------|-------------|
| `compliance_check` | Check device against compliance templates |
| `full_network_test` | End-to-end network validation |

[See all 35 tools →](docs/TOOLS.md)

## Architecture

```
┌─────────────────────────────────────────┐
│  AI Assistant (Claude, ChatGPT, etc.)   │
└────────────────┬────────────────────────┘
                 │ MCP Protocol (stdio/SSE)
┌────────────────▼────────────────────────┐
│  network_mcp_server.py                  │
│  FastMCP server + tool registry         │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  mcp_tools/                             │
│  ├── device.py      (9 tools)           │
│  ├── calculators.py (6 tools)           │
│  ├── topology.py    (6 tools)           │
│  ├── config.py      (8 tools)           │
│  ├── snmp.py        (5 tools)           │
│  ├── netconf.py     (4 tools)           │
│  ├── compliance.py  (7 tools)           │
│  └── ... (10 modules, 35 tools total)   │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  core/                                  │
│  ├── connection.py   (Netmiko/Scrapli)  │
│  ├── parser.py       (NTC/Genie)        │
│  ├── mtu_calculator.py                  │
│  └── subnet_calculator.py              │
└────────────────┬────────────────────────┘
                 │ SSH / NETCONF / SNMP
┌────────────────▼────────────────────────┐
│  Network Devices                        │
│  Cisco · Nokia · FRR · Juniper · Aruba  │
└─────────────────────────────────────────┘
```

## Project Structure

```
network-mcp/
├── network_mcp_server.py    # MCP server entry point
├── config/
│   └── devices.py           # Device inventory (env var overrides)
├── mcp_tools/               # All MCP tool implementations
│   ├── device.py            # Core device operations
│   ├── calculators.py       # MTU/subnet calculators
│   ├── topology.py          # LLDP discovery
│   ├── config.py            # Config backup/compare/rollback
│   ├── snmp.py              # SNMP polling
│   ├── netconf.py           # NETCONF operations
│   ├── compliance.py        # Compliance checking
│   └── ...                  # 10 modules, 35 tools total
├── core/                    # Connection and parsing libraries
├── templates/               # Jinja2 config templates (FRR, IOS-XE)
├── quickstart/              # Containerlab quick-start lab
└── tests/                   # Test suite
```

## Configuration

All configuration is via environment variables (or `.env` file):

```bash
# Device credentials
DEVICE_USERNAME=admin
DEVICE_PASSWORD=admin

# Device IPs (override defaults)
R1_HOST=10.255.255.11
R2_HOST=10.255.255.12

# Optional features
DEMO_MODE=true              # Mock data, no real devices
USE_NETBOX=true             # Pull inventory from NetBox
NETBOX_URL=http://localhost:8000
NETBOX_TOKEN=your-token
```

## Requirements

- Python 3.11+
- Network devices reachable via SSH/NETCONF/SNMP
- [Claude Desktop](https://claude.ai/download) or any MCP-compatible client

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
