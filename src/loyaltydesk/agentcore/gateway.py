"""Tool gateway with retries + scope checks (AgentCore gateway seam)."""

from __future__ import annotations

import time
from typing import Any

from loyaltydesk.tools.registry import invoke_tool


class ToolGateway:
    def __init__(self, *, max_attempts: int = 3, backoff_ms: list[int] | None = None) -> None:
        self.max_attempts = max_attempts
        self.backoff_ms = backoff_ms or [50, 150, 400]

    def call(
        self,
        name: str,
        args: dict[str, Any],
        *,
        granted_scopes: set[str],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = 0
        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            try:
                result = invoke_tool(name, args, granted_scopes=granted_scopes)
                return {
                    "name": name,
                    "args": args,
                    "result": result,
                    "attempts": attempts,
                    "ok": True,
                }
            except PermissionError as exc:
                # Auth / scope failures are not retryable.
                return {
                    "name": name,
                    "args": args,
                    "error": str(exc),
                    "attempts": attempts,
                    "ok": False,
                    "retryable": False,
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
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
        }


GATEWAY = ToolGateway()
