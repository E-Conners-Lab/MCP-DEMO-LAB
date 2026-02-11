# Quick-Start Lab

A minimal 2-router FRR lab for testing network-mcp in under 5 minutes.

## Prerequisites

- [containerlab](https://containerlab.dev/install/) installed
- Docker running

## Deploy

```bash
sudo containerlab deploy -t topology.clab.yml
```

This creates:
- **router1** (FRR 8.4.1) — 172.20.20.11, Loopback 198.51.100.1
- **router2** (FRR 8.4.1) — 172.20.20.12, Loopback 198.51.100.2
- OSPF peering on the eth1 link (10.0.12.0/30)

## Connect to network-mcp

Uncomment the containerlab devices in `config/devices.py`, or add to your `.env`:

```bash
# In the project root .env
DEVICE_USERNAME=root
DEVICE_PASSWORD=
```

## Verify

```bash
# Check OSPF neighbors
docker exec clab-quickstart-router1 vtysh -c "show ip ospf neighbor"

# Check routes
docker exec clab-quickstart-router1 vtysh -c "show ip route"
```

## Destroy

```bash
sudo containerlab destroy -t topology.clab.yml
```
