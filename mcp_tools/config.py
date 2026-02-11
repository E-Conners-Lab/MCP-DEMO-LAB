"""
Configuration management MCP tools.

- backup_config: Backup device running configuration
- list_backups: List available config backups
- compare_configs: Diff two configuration backups
- rollback_config: Restore a previous configuration

Backups are stored under ``BACKUP_BASE`` (``data/config_backups/``).
All file paths are validated via ``_validate_path_confined()`` to
prevent directory traversal attacks.

Symlink policy: paths are resolved via ``Path.resolve()`` then checked
for containment within BACKUP_BASE.  Symlinks that resolve outside the
backup directory are rejected and logged at WARNING level.
"""

import difflib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from config.devices import DEVICES
from core import log_event
from mcp_tools._shared import is_demo_mode, throttled

logger = logging.getLogger(__name__)

BACKUP_BASE = Path(os.getenv("BACKUP_BASE", "data/config_backups"))


def _validate_path_confined(path: str | Path, base: Path = BACKUP_BASE) -> Path:
    """Validate that a path is confined within the base directory.

    Resolves symlinks and ``..`` components, then checks that the
    resolved path starts with the resolved base directory.

    Raises:
        ValueError: If the path escapes the base directory
    """
    resolved_base = base.resolve()
    resolved_path = (base / path).resolve()

    if not str(resolved_path).startswith(str(resolved_base)):
        logger.warning(
            "Path traversal rejected: %r resolves to %s (outside %s)",
            str(path), resolved_path, resolved_base,
        )
        raise ValueError(f"Path '{path}' is outside the allowed directory")

    return resolved_path


async def backup_config(device_name: str) -> str:
    """
    Backup the running configuration of a device.

    Args:
        device_name: Device name from inventory

    Returns:
        JSON with backup path and timestamp
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "status": "success",
            "backup_file": f"backups/{device_name}_2026-02-10_120000.cfg",
            "size_bytes": 4523,
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    log_event(action="backup_config", details=device_name, status="start")

    try:
        from core.scrapli_manager import send_command

        raw_config = await throttled(send_command(device_name, "show running-config"))

        # Create backup file
        BACKUP_BASE.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        filename = f"{device_name}_{timestamp}.cfg"
        backup_path = _validate_path_confined(filename)

        backup_path.write_text(raw_config)
        size = backup_path.stat().st_size

        log_event(action="backup_config", details=f"{device_name}: {filename}", status="success")

        return json.dumps({
            "device": device_name,
            "status": "success",
            "backup_file": str(backup_path.relative_to(Path.cwd())),
            "size_bytes": size,
            "timestamp": timestamp,
        }, indent=2)

    except Exception as exc:
        log_event(action="backup_config", details=str(exc), status="error")
        return json.dumps({"error": f"Backup failed for {device_name}: {exc}"})


async def list_backups(device_name: str = None) -> str:
    """
    List available configuration backups.

    Args:
        device_name: Optional device name to filter (all devices if omitted)

    Returns:
        JSON with list of backup files and metadata
    """
    if is_demo_mode():
        return json.dumps({
            "backups": [
                {
                    "device": "R1", "file": "R1_2026-02-10.cfg",
                    "timestamp": "2026-02-10T12:00:00",
                },
                {
                    "device": "R1", "file": "R1_2026-02-09.cfg",
                    "timestamp": "2026-02-09T08:00:00",
                },
                {
                    "device": "R2", "file": "R2_2026-02-10.cfg",
                    "timestamp": "2026-02-10T12:00:00",
                },
            ],
            "total": 3,
        }, indent=2)

    try:
        if not BACKUP_BASE.exists():
            return json.dumps({"backups": [], "total": 0}, indent=2)

        backups = []
        for f in sorted(BACKUP_BASE.glob("*.cfg"), reverse=True):
            fname = f.name
            # Extract device name from filename (DeviceName_timestamp.cfg)
            parts = fname.rsplit("_", 2)
            dev_name = parts[0] if parts else fname

            if device_name and dev_name != device_name:
                continue

            stat = f.stat()
            backups.append({
                "device": dev_name,
                "file": fname,
                "size_bytes": stat.st_size,
                "timestamp": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })

        return json.dumps({"backups": backups, "total": len(backups)}, indent=2)

    except Exception as exc:
        return json.dumps({"error": f"Failed to list backups: {exc}"})


async def compare_configs(device_name: str, backup1: str = None, backup2: str = None) -> str:
    """
    Compare two configuration backups and show differences.

    Args:
        device_name: Device name
        backup1: First backup file (default: latest backup)
        backup2: Second backup file (default: current running config)

    Returns:
        JSON with unified diff and summary of changes
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "changes": [
                {"type": "added", "line": "interface Loopback99", "section": "interfaces"},
                {
                    "type": "added",
                    "line": " description Added by automation",
                    "section": "interfaces",
                },
            ],
            "summary": {"added": 2, "removed": 0, "modified": 0},
        }, indent=2)

    try:
        # Load backup1
        if backup1:
            path1 = _validate_path_confined(backup1)
            if not path1.exists():
                return json.dumps({"error": f"Backup file not found: {backup1}"})
            config1 = path1.read_text().splitlines()
            label1 = backup1
        else:
            # Find latest backup for device
            backups = sorted(BACKUP_BASE.glob(f"{device_name}_*.cfg"), reverse=True)
            if not backups:
                return json.dumps({"error": f"No backups found for {device_name}"})
            config1 = backups[0].read_text().splitlines()
            label1 = backups[0].name

        # Load backup2
        if backup2:
            path2 = _validate_path_confined(backup2)
            if not path2.exists():
                return json.dumps({"error": f"Backup file not found: {backup2}"})
            config2 = path2.read_text().splitlines()
            label2 = backup2
        else:
            # Get current running config
            from core.scrapli_manager import send_command
            raw = await throttled(send_command(device_name, "show running-config"))
            config2 = raw.splitlines()
            label2 = "running-config"

        # Generate diff
        diff = list(difflib.unified_diff(
            config1, config2,
            fromfile=label1, tofile=label2, lineterm="",
        ))

        added = sum(
            1 for line in diff
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1 for line in diff
            if line.startswith("-") and not line.startswith("---")
        )

        changes = []
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                changes.append({"type": "added", "line": line[1:]})
            elif line.startswith("-") and not line.startswith("---"):
                changes.append({"type": "removed", "line": line[1:]})

        return json.dumps({
            "device": device_name,
            "compared": {"from": label1, "to": label2},
            "changes": changes,
            "summary": {"added": added, "removed": removed, "total_changes": added + removed},
        }, indent=2)

    except Exception as exc:
        return json.dumps({"error": f"Compare failed for {device_name}: {exc}"})


async def rollback_config(device_name: str, backup_file: str) -> str:
    """
    Restore a device to a previous configuration backup.

    Args:
        device_name: Device name
        backup_file: Backup file to restore

    Returns:
        JSON with rollback status
    """
    if is_demo_mode():
        return json.dumps({
            "device": device_name,
            "status": "success",
            "restored_from": backup_file,
            "message": "[DEMO] Configuration restored",
        }, indent=2)

    device = DEVICES.get(device_name)
    if not device:
        return json.dumps({"error": f"Device '{device_name}' not found in inventory"})

    log_event(
        action="rollback_config",
        details=f"{device_name} from {backup_file}",
        status="start",
    )

    try:
        path = _validate_path_confined(backup_file)
        if not path.exists():
            return json.dumps({"error": f"Backup file not found: {backup_file}"})

        config_text = path.read_text()
        config_lines = [line for line in config_text.splitlines() if line.strip()]

        from core.scrapli_manager import send_config
        output = await throttled(send_config(device_name, config_lines))

        log_event(
            action="rollback_config",
            details=f"{device_name} from {backup_file}",
            status="success",
        )

        return json.dumps({
            "device": device_name,
            "status": "success",
            "restored_from": backup_file,
            "lines_applied": len(config_lines),
            "output": output,
        }, indent=2)

    except Exception as exc:
        log_event(action="rollback_config", details=str(exc), status="error")
        return json.dumps({"error": f"Rollback failed for {device_name}: {exc}"})


TOOLS = [
    {"fn": backup_config, "name": "backup_config", "category": "config"},
    {"fn": list_backups, "name": "list_backups", "category": "config"},
    {"fn": compare_configs, "name": "compare_configs", "category": "config"},
    {"fn": rollback_config, "name": "rollback_config", "category": "config"},
]
