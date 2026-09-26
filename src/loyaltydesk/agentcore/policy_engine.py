"""Gateway policy engine — Cedar-shaped allow/deny (AgentCore Policy seam).

Deterministic enforcement outside the model loop, matching AgentCore's
guidance that gateway policy stays enforceable even when the agent is unpredictable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyDecision:
    effect: str  # allow | deny
    reason: str
    rule_id: str


def evaluate_tool_call(
    *,
    tool_name: str,
    args: dict[str, Any],
    granted_scopes: set[str],
    required_scopes: set[str],
) -> PolicyDecision:
    if not required_scopes.issubset(granted_scopes):
        return PolicyDecision(
            effect="deny",
            reason=f"missing scopes {sorted(required_scopes - granted_scopes)}",
            rule_id="scope.enforce",
        )
    if tool_name == "run_sql":
        sql = str(args.get("sql", "")).lower()
        if any(tok in sql for tok in ("drop ", "delete ", "update ", "insert ", "alter ")):
            return PolicyDecision(
                effect="deny",
                reason="mutating SQL forbidden at gateway policy",
                rule_id="sql.readonly",
            )
    return PolicyDecision(effect="allow", reason="policy permit", rule_id="default.permit")


def evaluate_prompt(prompt: str) -> PolicyDecision:
    from loyaltydesk.guardrails.injection import detect_prompt_injection

    hits = detect_prompt_injection(prompt)
    if hits:
        return PolicyDecision(
            effect="deny",
            reason="; ".join(hits),
            rule_id="prompt.injection",
        )
    return PolicyDecision(effect="allow", reason="prompt ok", rule_id="prompt.permit")
