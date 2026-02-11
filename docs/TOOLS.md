# MCP Tools Reference

Complete list of all tools available in network-mcp.

## Device Operations (5 tools)

| Tool | Args | Description |
|------|------|-------------|
| `get_devices` | — | List all devices in inventory |
| `send_command` | `device_name`, `command` | Execute a show command |
| `send_config` | `device_name`, `commands` | Push config changes |
| `health_check` | `device_name` | Check single device health |
| `health_check_all` | — | Health check all devices in parallel |

## Calculators (6 tools)

| Tool | Args | Description |
|------|------|-------------|
| `calculate_tunnel_mtu` | `tunnel_type`, `physical_mtu`, `encryption`, `nat_traversal` | Calculate optimal VPN tunnel MTU |
| `get_mtu_scenarios` | — | Pre-calculated MTU for common scenarios |
| `calculate_subnet_info` | `address`, `netmask` | Subnet details from CIDR |
| `split_network` | `network`, `new_prefix` | VLSM subnet splitting |
| `get_subnet_reference` | — | Common subnet size reference table |
| `convert_netmask` | `value` | CIDR to dotted decimal conversion |

## Topology (3 tools)

| Tool | Args | Description |
|------|------|-------------|
| `discover_topology` | — | LLDP-based topology discovery |
| `lldp_neighbors` | `device_name` | LLDP neighbors for a device |
| `lldp_check_status` | `device_name` | Check LLDP status |

## Configuration (4 tools)

| Tool | Args | Description |
|------|------|-------------|
| `backup_config` | `device_name` | Backup running configuration |
| `list_backups` | `device_name` (optional) | List available backups |
| `compare_configs` | `device_name`, `backup1`, `backup2` | Diff two configs |
| `rollback_config` | `device_name`, `backup_file` | Restore previous config |

## Operations (3 tools)

| Tool | Args | Description |
|------|------|-------------|
| `bulk_command` | `command`, `device_names`, `device_type` | Run command across multiple devices |
| `ping_sweep` | `subnet`, `device_name` | Sweep subnet for reachable hosts |
| `traceroute` | `destination`, `device_name` | Trace route to destination |

## Interfaces (3 tools)

| Tool | Args | Description |
|------|------|-------------|
| `get_interface_status` | `device_name` | Interface status and stats |
| `get_arp_table` | `device_name` | ARP table entries |
| `get_mac_table` | `device_name` | MAC address table |

## Routing (2 tools)

| Tool | Args | Description |
|------|------|-------------|
| `get_routing_table` | `device_name`, `protocol` | Routing table entries |
| `get_neighbors` | `device_name`, `protocol` | BGP/OSPF neighbor status |

## NETCONF (3 tools)

| Tool | Args | Description |
|------|------|-------------|
| `get_interfaces_netconf` | `device_name` | Interface data via YANG |
| `get_bgp_neighbors_netconf` | `device_name` | BGP state via YANG |
| `get_netconf_capabilities` | `device_name` | NETCONF capabilities |

## SNMP (3 tools)

| Tool | Args | Description |
|------|------|-------------|
| `snmp_get_oid` | `device_name`, `oid` | SNMP GET specific OID |
| `snmp_walk_oid` | `device_name`, `oid` | SNMP WALK subtree |
| `snmp_poll_metrics` | `device_name` | Poll CPU/memory/interface metrics |

## Compliance (2 tools)

| Tool | Args | Description |
|------|------|-------------|
| `compliance_check` | `device_name`, `template` | Check against compliance template |
| `full_network_test` | — | End-to-end network validation |
