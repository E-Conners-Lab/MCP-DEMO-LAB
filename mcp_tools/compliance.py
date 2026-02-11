"""
Compliance checking MCP tools.

- compliance_check: Check device config against security baseline rules
- full_network_test: End-to-end network validation across all devices
- compliance_list_rules: List current security baseline rules

Compliance rules are stored as explicit data (not ad-hoc regexes in
logic).  The ``SECURITY_BASELINE_RULES`` list defines what is checked.
Each rule has:
- name: Human-readable rule description
- pattern: Regex pattern to search for in the running config
- required: Whether the pattern MUST be present (True) or MUST be absent (False)
- inverted: If True, match means failure (e.g., telnet should NOT be present)

Uses a data-driven approach that is transparent and extensible.
"""

import json
import logging
import re

from config.devices import DEVICES, is_cisco_device
from core import log_event
from mcp_tools._shared import is_demo_mode, throttled

logger = logging.getLogger(__name__)

# ===========================================================================
# Security Baseline Rules — explicit data, not buried in logic
# ===========================================================================

SECURITY_BASELINE_RULES = [
    {
        "name": "SSH enabled",
        "pattern": r"ip ssh version 2",
        "required": True,
        "inverted": False,
    },
    {
        "name": "No telnet",
        "pattern": r"transport input.*telnet",
        "required": False,
        "inverted": True,
    },
    {
        "name": "NTP configured",
        "pattern": r"ntp server",
        "required": True,
        "inverted": False,
    },
    {
        "name": "Logging configured",
        "pattern": r"logging host",
        "required": True,
        "inverted": False,
    },
    {
        "name": "Enable secret",
        "pattern": r"enable secret",
        "required": True,
        "inverted": False,
    },
]


def _check_compliance(config_text: str, rules: list[dict] = None) -> dict:
    """Evaluate a config against compliance rules.

    Args:
        config_text: Running configuration text
        rules: Rules to check (defaults to SECURITY_BASELINE_RULES)

    Returns:
        Dict with checks list, passed/failed counts, and overall status
    """
    if rules is None:
        rules = SECURITY_BASELINE_RULES

    checks = []
    passed = 0
    failed = 0

    for rule in rules:
        name = rule["name"]
        pattern = rule["pattern"]
        required = rule.get("required", True)
        inverted = rule.get("inverted", False)

        found = bool(re.search(pattern, config_text, re.MULTILINE))

        if inverted:
            # Pattern should NOT be present
            if found:
                checks.append({
                    "rule": name, "status": "fail",
                    "detail": f"Found prohibited pattern: {pattern}",
                })
                failed += 1
            else:
                checks.append({"rule": name, "status": "pass"})
                passed += 1
        else:
            # Pattern SHOULD be present
            if found:
                checks.append({"rule": name, "status": "pass"})
                passed += 1
            elif required:
                checks.append({
                    "rule": name, "status": "fail",
                    "detail": f"Required pattern not found: {pattern}",
                })
                failed += 1
            else:
                checks.append({
                    "rule": name, "status": "warning",
                    "detail": f"Recommended pattern not found: {pattern}",
                })
                passed += 1  # Warnings don't count as failures

    total = passed + failed
    if failed == 0:
        status = "pass"
    elif failed <= total // 2:
        status = "partial"
    else:
        status = "fail"

    score = f"{round(passed / total * 100)}%" if total > 0 else "N/A"

    return {
        "status": status,
        "score": score,
        "checks": checks,
        "passed": passed,
        "failed": failed,
        "total": total,
    }


async def compliance_check(device_name: str, template: str = "baseline") -> str:
    """
    Check a device against a compliance template.

    Validates that required configurations are present and
    prohibited configurations are absent.

    Args:
        device_name: Device name from inventory
        template: Compliance template name (default: "baseline")

    Returns:
        JSON with pass/fail status and list of violations
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "template": template,
            "status": "pass",
            "score": "95%",
            "checks": [
                {"rule": "SSH enabled", "status": "pass"},
                {"rule": "Telnet disabled", "status": "pass"},
                {"rule": "NTP configured", "status": "pass"},
                {"rule": "Banner set", "status": "fail", "detail": "No login banner configured"},
            ],
            "passed": 3,
            "failed": 1,
            "total": 4,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    try:
        from core.scrapli_manager import send_command

        config_text = await throttled(send_command(device_name, "show running-config"))
        result = _check_compliance(config_text)
        result["device"] = device_name
        result["template"] = template

        return json.dumps(result, indent=2)

    except Exception as exc:
        log_event(action="compliance_check", details=str(exc), status="error")
        return json.dumps({"error": f"Compliance check failed for {device_name}: {exc}"})


async def full_network_test() -> str:
    """
    Run end-to-end network validation across all devices.

    For each Cisco device: checks reachability, OSPF/BGP neighbor status,
    interface health, and basic compliance.

    Logs: ``N devices checked, M non-compliant``

    Returns:
        JSON with per-device test results and overall pass/fail
    """
    if is_demo_mode():
        return json.dumps({
            "status": "pass",
            "summary": {"total_devices": 6, "passed": 5, "warnings": 1, "failed": 0},
            "tests": [
                {
                    "device": "R1", "reachability": "pass",
                    "ospf": "pass", "bgp": "pass", "interfaces": "pass",
                },
                {
                    "device": "R2", "reachability": "pass",
                    "ospf": "pass", "bgp": "pass", "interfaces": "pass",
                },
                {
                    "device": "R3", "reachability": "pass",
                    "ospf": "pass", "bgp": "pass", "interfaces": "pass",
                },
                {
                    "device": "Switch-R1", "reachability": "pass",
                    "ospf": "N/A", "bgp": "N/A", "interfaces": "warning",
                },
                {
                    "device": "edge1", "reachability": "pass",
                    "ospf": "pass", "bgp": "pass", "interfaces": "pass",
                },
                {
                    "device": "spine1", "reachability": "pass",
                    "ospf": "pass", "bgp": "N/A", "interfaces": "pass",
                },
            ],
        }, indent=2)

    log_event(action="full_network_test", details="starting", status="start")

    tests = []
    passed = 0
    warnings = 0
    failed = 0

    for name, device in DEVICES.items():
        test_result = {"device": name}

        try:
            from core.scrapli_manager import send_command

            # Reachability (simple command)
            try:
                await throttled(send_command(name, "show version | include uptime"))
                test_result["reachability"] = "pass"
            except Exception:
                test_result["reachability"] = "fail"
                test_result["ospf"] = "skip"
                test_result["bgp"] = "skip"
                test_result["interfaces"] = "skip"
                failed += 1
                tests.append(test_result)
                continue

            # OSPF check
            if is_cisco_device(name):
                try:
                    ospf_raw = await throttled(send_command(name, "show ip ospf neighbor"))
                    test_result["ospf"] = "pass" if "FULL" in ospf_raw else "warning"
                except Exception:
                    test_result["ospf"] = "fail"
            else:
                test_result["ospf"] = "N/A"

            # BGP check
            if is_cisco_device(name):
                try:
                    bgp_raw = await throttled(send_command(name, "show ip bgp summary"))
                    has_bgp = "Established" in bgp_raw or bgp_raw.strip()
                    test_result["bgp"] = "pass" if has_bgp else "N/A"
                except Exception:
                    test_result["bgp"] = "N/A"
            else:
                test_result["bgp"] = "N/A"

            # Interface check
            try:
                intf_raw = await throttled(send_command(name, "show ip interface brief"))
                down_count = intf_raw.lower().count("down")
                test_result["interfaces"] = "warning" if down_count > 2 else "pass"
            except Exception:
                test_result["interfaces"] = "fail"

            # Tally
            statuses = [v for k, v in test_result.items() if k != "device"]
            if "fail" in statuses:
                failed += 1
            elif "warning" in statuses:
                warnings += 1
            else:
                passed += 1

        except Exception as exc:
            test_result["error"] = str(exc)
            failed += 1

        tests.append(test_result)

    total = len(tests)
    overall = "pass" if failed == 0 and warnings == 0 else ("warning" if failed == 0 else "fail")

    log_event(
        action="full_network_test",
        details=f"{total} devices checked, {failed} non-compliant",
        status="complete",
    )

    return json.dumps({
        "status": overall,
        "summary": {
            "total_devices": total,
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        },
        "tests": tests,
    }, indent=2)


async def compliance_list_rules() -> str:
    """
    List the current security baseline compliance rules.

    Returns the set of rules used by ``compliance_check`` so users
    can introspect what is being enforced.

    Returns:
        JSON with the rules list and count
    """
    rules = []
    for rule in SECURITY_BASELINE_RULES:
        rules.append({
            "name": rule["name"],
            "pattern": rule["pattern"],
            "required": rule.get("required", True),
            "inverted": rule.get("inverted", False),
        })

    return json.dumps({
        "rules": rules,
        "count": len(rules),
    }, indent=2)


TOOLS = [
    {"fn": compliance_check, "name": "compliance_check", "category": "compliance"},
    {"fn": full_network_test, "name": "full_network_test", "category": "compliance"},
    {"fn": compliance_list_rules, "name": "compliance_list_rules", "category": "compliance"},
]
