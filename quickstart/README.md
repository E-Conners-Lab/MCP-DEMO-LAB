# Quick-Start Lab

A minimal 2-router FRR lab for testing network-mcp in under 5 minutes.

## Prerequisites

- Docker running
- [containerlab](https://containerlab.dev/install/) (Linux only) **or** Docker Compose (macOS/Windows)

## Deploy

### Option A: Docker Compose (macOS / Windows / Linux)

```bash
docker compose up -d
```

### Option B: Containerlab (Linux only)

```bash
sudo containerlab deploy -t topology.clab.yml
```

This creates:
- **router1** (FRR 8.4.1) — Loopback 198.51.100.1
- **router2** (FRR 8.4.1) — Loopback 198.51.100.2
- OSPF peering on the eth1 link (10.0.12.0/30)

## Connect to network-mcp

Enable the quickstart devices in `config/devices.py` (they're commented out by default), then start the MCP server:

```bash
python network_mcp_server.py
```

## Verify

```bash
# Check OSPF neighbors
docker exec router1 vtysh -c "show ip ospf neighbor"

# Check routes
docker exec router1 vtysh -c "show ip route"
```

## Destroy

```bash
# Docker Compose
docker compose down

# Containerlab
sudo containerlab destroy -t topology.clab.yml
```
