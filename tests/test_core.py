"""Tests for PR 1 — core modules and config helpers."""

import os
import time

import pytest

os.environ["DEMO_MODE"] = "true"


# ============================================================================
# config/devices.py — get_scrapli_device, is_linux_device
# ============================================================================

class TestConfigDevices:
    def test_get_scrapli_device_not_found(self):
        from config.devices import get_scrapli_device
        assert get_scrapli_device("nonexistent") is None

    def test_is_linux_device_not_found(self):
        from config.devices import is_linux_device
        assert is_linux_device("nonexistent") is False

    def test_is_cisco_device(self):
        from config.devices import is_cisco_device
        # With empty inventory, all lookups return False
        assert is_cisco_device("R1") is False

    def test_get_scrapli_device_with_inventory(self, monkeypatch):
        """Test get_scrapli_device with a mocked device in inventory."""
        from config import devices

        fake_devices = {
            "TestRouter": {
                "device_type": "cisco_xe",
                "host": "192.168.1.1",
                "username": "admin",
                "password": "admin",
            }
        }
        monkeypatch.setattr(devices, "DEVICES", fake_devices)

        result = devices.get_scrapli_device("TestRouter")
        assert result is not None
        assert result["host"] == "192.168.1.1"
        assert result["platform"] == "cisco_iosxe"
        assert result["transport"] == "asyncssh"
        assert result["auth_strict_key"] is False

    def test_is_linux_device_with_inventory(self, monkeypatch):
        from config import devices

        fake_devices = {
            "linux-host": {"device_type": "linux", "host": "10.0.0.1"},
            "clab-host": {"device_type": "containerlab_linux", "host": "10.0.0.2"},
            "router": {"device_type": "cisco_xe", "host": "10.0.0.3"},
        }
        monkeypatch.setattr(devices, "DEVICES", fake_devices)

        assert devices.is_linux_device("linux-host") is True
        assert devices.is_linux_device("clab-host") is True
        assert devices.is_linux_device("router") is False


# ============================================================================
# core/device_cache.py — TTL expiry
# ============================================================================

class TestDeviceCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        from core.device_cache import clear, get, set
        await clear()
        await set("test_key", {"data": "value"})
        result = await get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_missing(self):
        from core.device_cache import clear, get
        await clear()
        result = await get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        from core.device_cache import _cache, _lock, clear, get, set
        await clear()
        await set("expiring", "value", ttl=1)

        # Should be present immediately
        result = await get("expiring")
        assert result == "value"

        # Manually expire the entry by backdating
        async with _lock:
            _cache["expiring"]["expires_at"] = time.monotonic() - 1

        # Should be expired now
        result = await get("expiring")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        from core.device_cache import clear, delete, get, set
        await clear()
        await set("to_delete", "value")
        assert await delete("to_delete") is True
        assert await delete("to_delete") is False
        assert await get("to_delete") is None

    @pytest.mark.asyncio
    async def test_clear(self):
        from core.device_cache import clear, set
        await set("a", 1)
        await set("b", 2)
        count = await clear()
        assert count >= 2

    @pytest.mark.asyncio
    async def test_stats(self):
        from core.device_cache import clear, set, stats
        await clear()
        await set("x", 1)
        s = await stats()
        assert s["total_entries"] == 1
        assert s["active_entries"] == 1


# ============================================================================
# core/circuit_breaker.py — state transitions
# ============================================================================

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=3, cooldown=1)
        assert cb.state == State.CLOSED
        assert await cb.is_call_permitted() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=3, cooldown=1)

        for _ in range(3):
            await cb.record_failure()

        assert cb.state == State.OPEN
        assert await cb.is_call_permitted() is False

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=2, cooldown=0)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == State.OPEN

        # Cooldown is 0, so it should transition to HALF_OPEN immediately
        assert await cb.is_call_permitted() is True
        assert cb.state == State.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=2, cooldown=0)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == State.OPEN

        # Transition to HALF_OPEN
        await cb.is_call_permitted()
        assert cb.state == State.HALF_OPEN

        # Success closes it
        await cb.record_success()
        assert cb.state == State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=2, cooldown=0)

        await cb.record_failure()
        await cb.record_failure()
        await cb.is_call_permitted()  # → HALF_OPEN
        assert cb.state == State.HALF_OPEN

        await cb.record_failure()
        assert cb.state == State.OPEN

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        from core.circuit_breaker import CircuitBreaker, State
        cb = CircuitBreaker("test", failure_threshold=2, cooldown=60)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == State.OPEN

        await cb.reset()
        assert cb.state == State.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_get_state(self):
        from core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test_device", failure_threshold=5, cooldown=30)
        state = cb.get_state()
        assert state["name"] == "test_device"
        assert state["state"] == "closed"
        assert state["failure_threshold"] == 5

    @pytest.mark.asyncio
    async def test_get_breaker_registry(self):
        from core.circuit_breaker import get_breaker
        cb = await get_breaker("test_device_registry")
        assert cb.name == "test_device_registry"

        # Same device returns same instance
        cb2 = await get_breaker("test_device_registry")
        assert cb is cb2


# ============================================================================
# core/containerlab.py — _validate_shell_safe
# ============================================================================

class TestContainerlab:
    def test_validate_safe_string(self):
        from core.containerlab import _validate_shell_safe
        assert _validate_shell_safe("clab-quickstart-router1") is True
        assert _validate_shell_safe("show ip route") is True
        assert _validate_shell_safe("vtysh -c show ip ospf neighbor") is True

    def test_validate_unsafe_string(self):
        from core.containerlab import _validate_shell_safe
        assert _validate_shell_safe("cmd; rm -rf /") is False
        assert _validate_shell_safe("cmd | cat /etc/passwd") is False
        assert _validate_shell_safe("cmd && evil") is False
        assert _validate_shell_safe("$(whoami)") is False
        assert _validate_shell_safe("`whoami`") is False
        assert _validate_shell_safe("cmd > /tmp/out") is False
        assert _validate_shell_safe("cmd < /tmp/in") is False

    def test_validate_empty_string(self):
        from core.containerlab import _validate_shell_safe
        assert _validate_shell_safe("") is False


# ============================================================================
# Import smoke tests
# ============================================================================

class TestCoreImports:
    def test_scrapli_manager_importable(self):
        from core.scrapli_manager import get_ios_xe_connection
        assert callable(get_ios_xe_connection)

    def test_netmiko_manager_importable(self):
        from core.netmiko_manager import send_command
        assert callable(send_command)

    def test_netconf_client_importable(self):
        from core.netconf_client import get_config
        assert callable(get_config)

    def test_unified_parser_importable(self):
        from core.unified_parser import parse_cli_output
        assert callable(parse_cli_output)

    def test_normalizers_importable(self):
        from core.normalizers import normalize_interface_name
        assert callable(normalize_interface_name)

    def test_device_cache_importable(self):
        from core.device_cache import get
        assert callable(get)

    def test_circuit_breaker_importable(self):
        from core.circuit_breaker import get_breaker
        assert callable(get_breaker)

    def test_containerlab_importable(self):
        from core.containerlab import run_command
        assert callable(run_command)

    def test_lldp_importable(self):
        from core.lldp import discover_lldp_neighbors
        assert callable(discover_lldp_neighbors)

    def test_mtu_calculator_importable(self):
        from core.mtu_calculator import calculate_mtu
        assert callable(calculate_mtu)

    def test_subnet_calculator_importable(self):
        from core.subnet_calculator import calculate_subnet
        assert callable(calculate_subnet)

    def test_core_init_log_event(self):
        from core import log_event
        # Should not raise
        log_event(action="test", details="testing", status="ok")


# ============================================================================
# core/normalizers.py — unit tests
# ============================================================================

class TestNormalizers:
    def test_normalize_interface_name(self):
        from core.normalizers import normalize_interface_name
        assert normalize_interface_name("Gi0/1") == "GigabitEthernet0/1"
        assert normalize_interface_name("Fa0/1") == "FastEthernet0/1"
        assert normalize_interface_name("Lo0") == "Loopback0"
        assert normalize_interface_name("Te0/0/0") == "TenGigabitEthernet0/0/0"
        assert normalize_interface_name("Vl100") == "Vlan100"
        assert normalize_interface_name("GigabitEthernet0/1") == "GigabitEthernet0/1"

    def test_normalize_mac_address(self):
        from core.normalizers import normalize_mac_address
        assert normalize_mac_address("aabb.ccdd.eeff") == "aa:bb:cc:dd:ee:ff"
        assert normalize_mac_address("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
        assert normalize_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_clean_output(self):
        from core.normalizers import clean_output
        raw = "hello\x1b[0m world  \n  line2  \n"
        result = clean_output(raw)
        assert "\x1b" not in result
        assert result == "hello world\n  line2"
