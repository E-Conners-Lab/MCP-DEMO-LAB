"""Circuit breaker for device connections.

Prevents repeated connection attempts to unreachable devices by tracking
consecutive failures and temporarily blocking calls.

State machine: CLOSED → OPEN → HALF_OPEN → CLOSED

Semantics:
- **State transitions**: Trips OPEN after ``failure_threshold`` consecutive
  failures.  After ``cooldown_seconds``, transitions to HALF_OPEN.  A
  single success in HALF_OPEN resets to CLOSED.  A failure in HALF_OPEN
  returns to OPEN.
- **Reset on restart**: All state is lost on process restart (intentional —
  no Redis persistence).
- **Concurrency**: Single-process MCP server; ``asyncio.Lock`` guards state
  mutations.

Deployment note: Behavior is per-process and non-persistent. Typical
deployment is a single MCP server instance.
"""

import asyncio
import logging
import os
import time
from enum import Enum

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
COOLDOWN_SECONDS = int(os.getenv("CB_COOLDOWN_SECONDS", "30"))


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-device circuit breaker.

    Usage::

        cb = get_breaker("R1")
        if cb.is_call_permitted():
            try:
                result = await connect(...)
                cb.record_success()
            except Exception:
                cb.record_failure()
        else:
            raise RuntimeError("Circuit breaker open for R1")
    """

    def __init__(self, name: str, failure_threshold: int = FAILURE_THRESHOLD,
                 cooldown: int = COOLDOWN_SECONDS):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.state = State.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0
        self._lock = asyncio.Lock()

    async def is_call_permitted(self) -> bool:
        """Check if a call is allowed through the breaker."""
        async with self._lock:
            if self.state == State.CLOSED:
                return True
            if self.state == State.OPEN:
                if time.monotonic() - self.last_failure_time >= self.cooldown:
                    self.state = State.HALF_OPEN
                    logger.info("Circuit breaker %s: OPEN → HALF_OPEN", self.name)
                    return True
                return False
            # HALF_OPEN: allow one probe call
            return True

    async def record_success(self) -> None:
        """Record a successful call — resets the breaker to CLOSED."""
        async with self._lock:
            if self.state in (State.HALF_OPEN, State.CLOSED):
                self.state = State.CLOSED
                self.failure_count = 0
                logger.debug("Circuit breaker %s: → CLOSED", self.name)

    async def record_failure(self) -> None:
        """Record a failed call — may trip the breaker to OPEN."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()

            if self.state == State.HALF_OPEN:
                self.state = State.OPEN
                logger.warning("Circuit breaker %s: HALF_OPEN → OPEN", self.name)
            elif self.failure_count >= self.failure_threshold:
                self.state = State.OPEN
                logger.warning(
                    "Circuit breaker %s: CLOSED → OPEN (failures=%d)",
                    self.name, self.failure_count,
                )

    async def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        async with self._lock:
            self.state = State.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0

    def get_state(self) -> dict:
        """Return current breaker state as a dict."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown,
        }


# Global registry of per-device circuit breakers
_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


async def get_breaker(device_name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a device."""
    async with _registry_lock:
        if device_name not in _breakers:
            _breakers[device_name] = CircuitBreaker(device_name)
        return _breakers[device_name]


async def reset_all() -> int:
    """Reset all circuit breakers. Returns count reset."""
    async with _registry_lock:
        count = len(_breakers)
        for cb in _breakers.values():
            await cb.reset()
        return count
