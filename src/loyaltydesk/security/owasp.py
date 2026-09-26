"""OWASP LLM Top 10 control matrix for LoyaltyDesk.

Source: https://owasp.org/www-project-top-10-for-large-language-model-applications/
"""

from __future__ import annotations

from typing import Any

CONTROLS: list[dict[str, Any]] = [
    {
        "id": "LLM01",
        "name": "Prompt Injection",
        "status": "mitigated",
        "controls": ["guardrails.injection", "agentcore.policy.allow_request"],
    },
    {
        "id": "LLM02",
        "name": "Insecure Output Handling",
        "status": "mitigated",
        "controls": ["models.AnalystAnswer", "guardrails.pipeline.apply_output_guardrails"],
    },
    {
        "id": "LLM03",
        "name": "Training Data Poisoning",
        "status": "out_of_scope_demo",
        "controls": ["seeded warehouse only; no user-writable knowledge in demo"],
    },
    {
        "id": "LLM04",
        "name": "Model Denial of Service",
        "status": "mitigated",
        "controls": ["gateway.circuit_breaker", "gateway.rate_limit"],
    },
    {
        "id": "LLM05",
        "name": "Supply Chain Vulnerabilities",
        "status": "partial",
        "controls": ["uv.lock pinned deps", "CI eval regression"],
    },
    {
        "id": "LLM06",
        "name": "Sensitive Information Disclosure",
        "status": "mitigated",
        "controls": ["guardrails.pii", "member_snapshot strips email from answer path"],
    },
    {
        "id": "LLM07",
        "name": "Insecure Plugin Design",
        "status": "mitigated",
        "controls": ["tools.registry Pydantic schemas", "tool_scope authz"],
    },
    {
        "id": "LLM08",
        "name": "Excessive Agency",
        "status": "mitigated",
        "controls": ["read_only_sql", "HITL interrupt for mutations", "policy_engine"],
    },
    {
        "id": "LLM09",
        "name": "Overreliance / Misinformation",
        "status": "mitigated",
        "controls": ["reflection", "evals.metrics.groundedness", "require evidence"],
    },
    {
        "id": "LLM10",
        "name": "Model Theft",
        "status": "out_of_scope_demo",
        "controls": ["no model weights hosted"],
    },
]


def control_matrix() -> dict[str, Any]:
    mitigated = sum(1 for c in CONTROLS if c["status"] == "mitigated")
    return {
        "framework": "OWASP Top 10 for LLM Applications",
        "mitigated": mitigated,
        "total": len(CONTROLS),
        "controls": CONTROLS,
    }
