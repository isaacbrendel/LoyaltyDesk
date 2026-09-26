"""Amazon AgentCore-shaped packaging for the LoyaltyDesk harness.

This is a portable manifest of runtime, gateway tools, memory, policy,
skills, and subagents — the same seams you'd wire into AgentCore Runtime
(Bedrock) in a production AWS account.
"""

from __future__ import annotations

from typing import Any

from loyaltydesk import __version__
from loyaltydesk.tools.registry import TOOL_SPECS

MANIFEST: dict[str, Any] = {
    "name": "loyaltydesk-analyst",
    "version": __version__,
    "description": (
        "Internal loyalty analyst agent: SQL over program data, handbook retrieval, "
        "and earn/burn logic with structured outputs."
    ),
    "runtime": {
        "kind": "agentcore-compatible",
        "entrypoint": "loyaltydesk.agentcore.runtime:invoke",
        "language": "python",
        "streaming": True,
        "structured_output": "loyaltydesk.models:AnalystAnswer",
    },
    "memory": {
        "short_term": "session_transcript",
        "long_term": "none_in_demo",
        "ttl_minutes": 120,
    },
    "policy": {
        "module": "loyaltydesk.agentcore.policy",
        "rules": [
            "block_prompt_injection",
            "read_only_sql",
            "tool_scope_enforcement",
            "pii_redaction",
            "hitl_for_program_mutations",
        ],
    },
    "observability": {
        "traces": "jsonl",
        "compatible_with": ["OpenTelemetry", "Langfuse", "CloudWatch", "LangSmith"],
        "span_prefix": "loyaltydesk",
    },
    "gateway": {
        "module": "loyaltydesk.agentcore.gateway",
        "retries": {"max_attempts": 3, "backoff_ms": [50, 150, 400]},
        "tools": TOOL_SPECS,
    },
    "skills": [
        {
            "id": "program_sql",
            "description": "Answer quantitative loyalty questions with evidence-backed SQL.",
            "tools": ["run_sql", "member_snapshot", "ask_semantic"],
        },
        {
            "id": "handbook_rag",
            "description": "Retrieve earn/burn/campaign policy with citations.",
            "tools": ["search_knowledge", "explain_loyalty_rule"],
        },
        {
            "id": "churn_playbook",
            "description": "Identify inactive members and recommend win-back offers.",
            "tools": ["run_sql", "search_knowledge"],
        },
    ],
    "subagents": [
        {
            "id": "supervisor",
            "pattern": "router",
            "handoff": ["sql_analyst", "knowledge", "loyalty_logic"],
        },
        {
            "id": "sql_analyst",
            "pattern": "tool_caller",
            "skills": ["program_sql", "churn_playbook"],
        },
        {
            "id": "knowledge",
            "pattern": "rag",
            "skills": ["handbook_rag"],
        },
        {
            "id": "loyalty_logic",
            "pattern": "domain_expert",
            "skills": ["handbook_rag"],
        },
        {
            "id": "reflector",
            "pattern": "reflection",
            "purpose": "Check evidence coverage and hallucination risk before return.",
        },
        {
            "id": "hitl_gate",
            "pattern": "human_in_the_loop",
            "purpose": "Pause on program-mutation proposals until an analyst approves.",
        },
    ],
    "when_not_to_use_agents": [
        "Simple CRUD lookups with a fixed SQL template — call the tool directly.",
        "Bulk ETL / batch scoring — use a job, not a chat agent.",
        "Questions outside loyalty program scope — refuse rather than invent.",
    ],
}


def get_manifest() -> dict[str, Any]:
    return MANIFEST
