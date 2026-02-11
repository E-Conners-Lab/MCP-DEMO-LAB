"""Tests for PR 3b — compliance rules and config path security."""

import json
import os
import tempfile
from pathlib import Path

import pytest

os.environ["DEMO_MODE"] = "true"


# ============================================================================
# Compliance: _check_compliance with synthetic configs
# ============================================================================

class TestComplianceRules:
    """Test compliance rule evaluation with small synthetic configs."""

    def test_fully_compliant(self):
        from mcp_tools.compliance import _check_compliance

        config = """
hostname R1
enable secret 0 SuperSecret
ip ssh version 2
ntp server 10.0.0.1
logging host 10.0.0.2
line vty 0 4
 transport input ssh
"""
        result = _check_compliance(config)
        assert result["status"] == "pass"
        assert result["failed"] == 0
        assert result["passed"] == 5

    def test_partially_compliant(self):
        from mcp_tools.compliance import _check_compliance

        config = """
hostname R1
enable secret 0 SuperSecret
ip ssh version 2
line vty 0 4
 transport input ssh
"""
        # Missing NTP and logging
        result = _check_compliance(config)
        assert result["status"] == "partial"
        assert result["failed"] == 2  # NTP + logging
        assert result["passed"] == 3  # SSH + no telnet + enable secret

    def test_non_compliant(self):
        from mcp_tools.compliance import _check_compliance

        config = """
hostname R1
line vty 0 4
 transport input telnet ssh
"""
        # Missing SSH, NTP, logging, enable secret; telnet present
        result = _check_compliance(config)
        assert result["status"] == "fail"
        assert result["failed"] >= 4

    def test_inverted_rule_telnet_present(self):
        from mcp_tools.compliance import _check_compliance

        config = """
hostname R1
enable secret 0 SuperSecret
ip ssh version 2
ntp server 10.0.0.1
logging host 10.0.0.2
line vty 0 4
 transport input telnet ssh
"""
        result = _check_compliance(config)
        # Telnet is present — should cause a failure
        telnet_check = [c for c in result["checks"] if c["rule"] == "No telnet"][0]
        assert telnet_check["status"] == "fail"

    def test_custom_rules(self):
        from mcp_tools.compliance import _check_compliance

        custom_rules = [
            {"name": "Banner set", "pattern": r"banner motd", "required": True, "inverted": False},
        ]
        config = "banner motd ^This is a warning^"
        result = _check_compliance(config, rules=custom_rules)
        assert result["status"] == "pass"
        assert result["passed"] == 1

    def test_empty_config(self):
        from mcp_tools.compliance import _check_compliance

        result = _check_compliance("")
        assert result["failed"] >= 3  # SSH, NTP, logging, enable secret missing

    @pytest.mark.asyncio
    async def test_compliance_list_rules(self):
        from mcp_tools.compliance import compliance_list_rules

        result = json.loads(await compliance_list_rules())
        assert "rules" in result
        assert result["count"] == 5
        assert all("name" in r and "pattern" in r for r in result["rules"])


# ============================================================================
# Config: _validate_path_confined edge cases
# ============================================================================

class TestPathValidation:
    """Test _validate_path_confined for directory traversal protection."""

    def test_valid_filename(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = _validate_path_confined("test.cfg", base=base)
            assert str(result).startswith(str(base.resolve()))

    def test_dotdot_traversal(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with pytest.raises(ValueError, match="outside the allowed directory"):
                _validate_path_confined("../../etc/passwd", base=base)

    def test_absolute_path_outside_base(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with pytest.raises(ValueError, match="outside the allowed directory"):
                _validate_path_confined("/etc/passwd", base=base)

    def test_deeply_nested_path(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Deeply nested but still within base — should work
            result = _validate_path_confined("a/b/c/d/test.cfg", base=base)
            assert str(result).startswith(str(base.resolve()))

    def test_symlink_inside_base(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create a real file and symlink within base
            real_file = base / "real.cfg"
            real_file.write_text("config")
            link_file = base / "link.cfg"
            link_file.symlink_to(real_file)

            result = _validate_path_confined("link.cfg", base=base)
            assert str(result).startswith(str(base.resolve()))

    def test_symlink_outside_base(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "backups"
            base.mkdir()

            # Create a symlink that points outside the base
            outside_file = Path(tmpdir) / "secret.cfg"
            outside_file.write_text("secret")
            link = base / "escape.cfg"
            link.symlink_to(outside_file)

            with pytest.raises(ValueError, match="outside the allowed directory"):
                _validate_path_confined("escape.cfg", base=base)

    def test_dotdot_in_middle_of_path(self):
        from mcp_tools.config import _validate_path_confined

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with pytest.raises(ValueError, match="outside the allowed directory"):
                _validate_path_confined("subdir/../../etc/passwd", base=base)


# ============================================================================
# Demo mode tests for new tools
# ============================================================================

class TestDemoModeNewTools:
    @pytest.mark.asyncio
    async def test_compliance_list_rules_demo(self):
        from mcp_tools.compliance import compliance_list_rules

        result = json.loads(await compliance_list_rules())
        assert "rules" in result
        assert result["count"] >= 5

    @pytest.mark.asyncio
    async def test_compare_configs_demo(self):
        from mcp_tools.config import compare_configs

        result = json.loads(await compare_configs("R1"))
        assert "changes" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_rollback_config_demo(self):
        from mcp_tools.config import rollback_config

        result = json.loads(await rollback_config("R1", "R1_backup.cfg"))
        assert result["status"] == "success"
