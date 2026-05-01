"""
Recovery Skill — circuit breakers, exponential back-off, graceful degradation,
and fallback strategy registration for all Gold Tier components.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

from .audit_logger import AuditLogger

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, Enum):
    CLOSED = "closed"        # normal operation
    OPEN = "open"            # failing fast
    HALF_OPEN = "half_open"  # probing recovery


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _success_in_half_open: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_in_half_open = 0
        return self._state

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._success_in_half_open += 1
            if self._success_in_half_open >= 2:
                self._state = CircuitState.CLOSED
                self._failures = 0
        elif self.state == CircuitState.CLOSED:
            self._failures = max(0, self._failures - 1)

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


@dataclass
class RecoveryResult:
    success: bool
    attempts: int
    last_error: Exception | None = None
    fallback_used: bool = False
    fallback_name: str | None = None
    result: Any = None


class RecoverySkill:
    """
    Centralised resilience layer.

    Usage:
        recovery = RecoverySkill()

        # Register a fallback for a skill action
        recovery.register_fallback("social.post_twitter", mock_post)

        # Wrap a coroutine with retry + circuit breaker
        result = await recovery.execute_with_recovery(
            "social", "post_twitter", coro_fn, *args
        )
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_multiplier: float = 2.0,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 60.0,
        logger: AuditLogger | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_multiplier = backoff_multiplier
        self._fallbacks: dict[str, Callable] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_recovery_timeout = circuit_recovery_timeout
        self._logger = logger or AuditLogger()
        self._error_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def register_fallback(self, key: str, fn: Callable) -> None:
        """Register fallback for 'skill.action' key."""
        self._fallbacks[key] = fn
        self._logger.log_state_change("recovery", "init", "ready", f"fallback registered: {key}")

    def get_circuit(self, key: str) -> CircuitBreaker:
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(
                name=key,
                failure_threshold=self._circuit_failure_threshold,
                recovery_timeout=self._circuit_recovery_timeout,
            )
        return self._breakers[key]

    async def execute_with_recovery(
        self,
        skill: str,
        action: str,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryResult:
        key = f"{skill}.{action}"
        breaker = self.get_circuit(key)
        result = RecoveryResult(success=False, attempts=0)

        if not breaker.allow_request():
            self._logger.log_state_change(key, CircuitState.OPEN, CircuitState.OPEN, "circuit open — fast fail")
            return await self._try_fallback(result, key, skill, action, *args, **kwargs)

        for attempt in range(1, self._max_retries + 1):
            result.attempts = attempt
            try:
                if asyncio.iscoroutinefunction(fn):
                    result.result = await fn(*args, **kwargs)
                else:
                    result.result = await asyncio.get_event_loop().run_in_executor(None, functools.partial(fn, *args, **kwargs))

                breaker.record_success()
                result.success = True
                old_state = breaker._state
                if old_state != CircuitState.CLOSED:
                    self._logger.log_state_change(key, old_state, breaker.state, "recovery success")
                return result

            except Exception as exc:
                result.last_error = exc
                breaker.record_failure()
                self._error_history[key].append({"ts": time.time(), "error": str(exc), "attempt": attempt})
                self._logger.log_error(skill, action, exc, severity="WARNING", recoverable=attempt < self._max_retries)

                if breaker.state == CircuitState.OPEN:
                    self._logger.log_state_change(key, CircuitState.CLOSED, CircuitState.OPEN, f"threshold hit after {attempt} failures")
                    return await self._try_fallback(result, key, skill, action, *args, **kwargs)

                if attempt < self._max_retries:
                    delay = self._backoff_base * (self._backoff_multiplier ** (attempt - 1))
                    self._logger.log_action("recovery", "backoff", {"attempt": attempt, "delay_s": delay, "key": key})
                    await asyncio.sleep(delay)

        return await self._try_fallback(result, key, skill, action, *args, **kwargs)

    def circuit_status(self) -> dict[str, str]:
        return {k: b.state.value for k, b in self._breakers.items()}

    def error_summary(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._error_history.items()}

    def reset_circuit(self, key: str) -> None:
        if key in self._breakers:
            self._breakers[key]._state = CircuitState.CLOSED
            self._breakers[key]._failures = 0
            self._logger.log_state_change(key, "open/half_open", CircuitState.CLOSED, "manual reset")

    # ------------------------------------------------------------------ #
    #  Internals                                                            #
    # ------------------------------------------------------------------ #

    async def _try_fallback(
        self,
        result: RecoveryResult,
        key: str,
        skill: str,
        action: str,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryResult:
        if key in self._fallbacks:
            try:
                fn = self._fallbacks[key]
                if asyncio.iscoroutinefunction(fn):
                    result.result = await fn(*args, **kwargs)
                else:
                    result.result = fn(*args, **kwargs)
                result.fallback_used = True
                result.fallback_name = key
                result.success = True
                self._logger.log_action("recovery", "fallback_used", {"key": key})
            except Exception as fb_exc:
                self._logger.log_error("recovery", "fallback", fb_exc, severity="ERROR", recoverable=False)
                result.success = False
        else:
            self._logger.log_error(skill, action, result.last_error or "no fallback registered", severity="CRITICAL", recoverable=False)
        return result

    # ------------------------------------------------------------------ #
    #  Decorator helper                                                     #
    # ------------------------------------------------------------------ #

    def with_recovery(self, skill: str, action: str) -> Callable[[F], F]:
        """Decorator: wraps an async function with retry + circuit breaker."""
        def decorator(fn: F) -> F:
            @functools.wraps(fn)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                res = await self.execute_with_recovery(skill, action, fn, *args, **kwargs)
                if not res.success:
                    raise RuntimeError(f"{skill}.{action} failed after {res.attempts} attempts — last: {res.last_error}")
                return res.result
            return wrapper  # type: ignore[return-value]
        return decorator
