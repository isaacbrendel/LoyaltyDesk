"""Runtime policy checks (AgentCore policy seam)."""

from __future__ import annotations

import re

from loyaltydesk.guardrails.injection import detect_prompt_injection
from loyaltydesk.guardrails.tool_scope import ANALYST_SCOPES, TOOL_SCOPES
from loyaltydesk.models import ToolName

# Analyst asks that imply mutating the live loyalty program → require HITL.
_MUTATION = re.compile(
    r"\b(approve|change earn|change burn|issue points|grant points|alter tier|"
    r"update multiplier|deploy campaign|push to production|mutate)\b",
    re.IGNORECASE,
)


def requires_hitl(question: str) -> bool:
    return bool(_MUTATION.search(question))


def allow_request(question: str) -> tuple[bool, list[str]]:
    notes = detect_prompt_injection(question)
    if notes:
        return False, notes
    return True, []


def default_scopes() -> set[str]:
    return set(ANALYST_SCOPES)


def tool_scopes(tool: ToolName) -> set[str]:
    return set(TOOL_SCOPES[tool])
