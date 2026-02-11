"""Containerlab interaction helpers.

Provides command execution on containerlab containers via ``docker exec``
and basic health checking.  All commands are validated against a safe-list
before execution to prevent shell injection.

Supported now:
- ``run_command(container, command)`` — run a command inside a container
- ``check_health(container)`` — basic reachability / process check
- ``_validate_shell_safe(value)`` — input sanitisation

Future expansion may include topology deploy/destroy helpers.
"""

import asyncio
import logging
import re
import shlex

logger = logging.getLogger(__name__)

# Characters allowed in container names and simple commands
_SAFE_PATTERN = re.compile(r'^[a-zA-Z0-9_.:\-/= ]+$')


def _validate_shell_safe(value: str) -> bool:
    """Return True if *value* contains only shell-safe characters.

    Rejects shell metacharacters (|, &, ;, $, `, etc.) to prevent
    command injection when composing ``docker exec`` invocations.
    """
    return bool(_SAFE_PATTERN.match(value))


async def run_command(container: str, command: str, *, frr: bool = False) -> str:
    """Execute *command* inside a containerlab container via ``docker exec``.

    Args:
        container: Docker container name (e.g. ``clab-quickstart-router1``)
        command: Command to execute inside the container
        frr: If True, wrap command with ``vtysh -c`` for FRRouting devices

    Returns:
        stdout from the command

    Raises:
        ValueError: If container name or command contains unsafe characters
        RuntimeError: If the docker exec command fails
    """
    if not _validate_shell_safe(container):
        raise ValueError(f"Unsafe container name: {container!r}")
    if not _validate_shell_safe(command):
        raise ValueError(f"Unsafe command: {command!r}")

    if frr:
        cmd = ["docker", "exec", container, "vtysh", "-c", command]
    else:
        cmd = ["docker", "exec", container] + shlex.split(command)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(f"docker exec failed (rc={proc.returncode}): {err}")

    return stdout.decode().strip()


async def check_health(container: str) -> dict:
    """Basic health check for a containerlab container.

    Returns a dict with ``reachable`` (bool) and ``output`` (str).
    """
    try:
        output = await run_command(container, "echo healthy")
        return {"reachable": True, "output": output}
    except Exception as exc:
        return {"reachable": False, "output": str(exc)}
