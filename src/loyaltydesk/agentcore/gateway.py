"""Tool gateway with retries, rate limit, circuit breaker, and policy (AgentCore Gateway)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from loyaltydesk.agentcore.policy_engine import evaluate_tool_call
from loyaltydesk.guardrails.tool_scope import TOOL_SCOPES
from loyaltydesk.models import ToolName
from loyaltydesk.tools.registry import invoke_tool


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.open_until = 0.0
        self._lock = Lock()

    def allow(self) -> bool:
        with self._lock:
            if time.time() < self.open_until:
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.open_until = time.time() + self.reset_seconds


class RateLimiter:
    def __init__(self, *, max_calls: int = 60, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_calls:
                return False
            q.append(now)
            return True


class ToolGateway:
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_ms: list[int] | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.backoff_ms = backoff_ms or [50, 150, 400]
        self.breaker = CircuitBreaker()
        self.limiter = RateLimiter()

    def call(
        self,
        name: str,
        args: dict[str, Any],
        *,
        granted_scopes: set[str],
        session_key: str = "default",
    ) -> dict[str, Any]:
        if not self.breaker.allow():
            return {
                "name": name,
                "args": args,
                "error": "circuit_breaker_open",
                "attempts": 0,
                "ok": False,
                "retryable": True,
                "policy": "deny",
            }
        if not self.limiter.allow(session_key):
            return {
                "name": name,
                "args": args,
                "error": "rate_limited",
                "attempts": 0,
                "ok": False,
                "retryable": True,
                "policy": "deny",
            }

        tool = ToolName(name)
        decision = evaluate_tool_call(
            tool_name=name,
            args=args,
            granted_scopes=granted_scopes,
            required_scopes=TOOL_SCOPES[tool],
        )
        if decision.effect == "deny":
            return {
                "name": name,
                "args": args,
                "error": decision.reason,
                "attempts": 0,
                "ok": False,
                "retryable": False,
                "policy": "deny",
                "rule_id": decision.rule_id,
            }

        last_error: Exception | None = None
        attempts = 0
        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            try:
                result = invoke_tool(name, args, granted_scopes=granted_scopes)
                self.breaker.record_success()
                return {
                    "name": name,
                    "args": args,
                    "result": result,
                    "attempts": attempts,
                    "ok": True,
                    "policy": "allow",
                    "rule_id": decision.rule_id,
                }
            except PermissionError as exc:
                self.breaker.record_failure()
                return {
                    "name": name,
                    "args": args,
                    "error": str(exc),
                    "attempts": attempts,
                    "ok": False,
                    "retryable": False,
                    "policy": "deny",
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.breaker.record_failure()
                if attempt < self.max_attempts:
                    delay = self.backoff_ms[min(attempt - 1, len(self.backoff_ms) - 1)]
                    time.sleep(delay / 1000.0)
        return {
            "name": name,
            "args": args,
            "error": str(last_error) if last_error else "unknown",
            "attempts": attempts,
            "ok": False,
            "retryable": True,
            "policy": "allow",
        }


GATEWAY = ToolGateway()
